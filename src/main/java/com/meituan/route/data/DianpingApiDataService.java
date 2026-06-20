package com.meituan.route.data;

import com.meituan.route.model.POI;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Profile;
import org.springframework.context.annotation.Primary;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

import java.time.Duration;
import java.time.LocalTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Real-time data service powered by 美团开放平台 (Meituan Open Platform).
 * Activated when Spring profile 'dianping' is active.
 *
 * Uses the Meituan merchant search API to fetch real POI data:
 *   - Business/POI search: /api/v1/poi/search
 *   - Business details:    /api/v1/poi/detail
 *
 * Authentication: Bearer token via Authorization header.
 */
@Service
@Profile("dianping")
@Primary
public class DianpingApiDataService implements DataService {

    private static final Logger log = LoggerFactory.getLogger(DianpingApiDataService.class);

    private final WebClient meituanClient;
    private final WebClient dianpingClient;
    private final String apiToken;
    private final GaodeGeoService gaodeGeoService;
    private final Map<String, List<POI>> cache = new ConcurrentHashMap<>();

    // Dianping API category codes -> our category mapping
    private static final Map<String, String> CATEGORY_MAP = Map.ofEntries(
            Map.entry("餐饮", "RESTAURANT"),
            Map.entry("美食", "RESTAURANT"),
            Map.entry("购物", "SHOPPING"),
            Map.entry("景点", "ATTRACTION"),
            Map.entry("旅游景点", "ATTRACTION"),
            Map.entry("娱乐", "ENTERTAINMENT"),
            Map.entry("休闲娱乐", "ENTERTAINMENT"),
            Map.entry("文化", "CULTURE"),
            Map.entry("文化传媒", "CULTURE"),
            Map.entry("运动", "SPORTS"),
            Map.entry("酒店", "HOTEL"),
            Map.entry("生活服务", "LIFE_SERVICE")
    );

    public DianpingApiDataService(
            WebClient.Builder builder,
            @Value("${meituan.api.token}") String apiToken,
            @Value("${meituan.api.base-url}") String meituanBaseUrl,
            @Value("${meituan.api.dianping-base-url}") String dianpingBaseUrl,
            GaodeGeoService gaodeGeoService) {
        this.apiToken = apiToken;
        this.gaodeGeoService = gaodeGeoService;
        this.meituanClient = builder
                .baseUrl(meituanBaseUrl)
                .defaultHeader("Authorization", "Bearer " + apiToken)
                .defaultHeader("Content-Type", MediaType.APPLICATION_JSON_VALUE)
                .build();
        this.dianpingClient = builder
                .baseUrl(dianpingBaseUrl)
                .defaultHeader("Authorization", "Bearer " + apiToken)
                .defaultHeader("Content-Type", MediaType.APPLICATION_JSON_VALUE)
                .build();
    }

    @PostConstruct
    void init() {
        log.info("DianpingApiDataService activated — connecting to Meituan Open Platform");
        log.info("API endpoint: {}", meituanClient.toString());
        // Pre-fetch Beijing POIs in background for faster first request
        new Thread(() -> {
            log.info("Pre-fetching Beijing POI data...");
            var beijingCategories = List.of("RESTAURANT", "ATTRACTION", "SHOPPING", "ENTERTAINMENT");
            for (String cat : beijingCategories) {
                searchByCategory("北京", null, cat)
                        .collectList()
                        .subscribe(
                                pois -> log.info("Pre-fetched {} POIs for category={} in Beijing", pois.size(), cat),
                                err -> log.warn("Pre-fetch failed for category={} in Beijing: {}", cat, err.getMessage())
                        );
            }
        }, "beijing-prefetch").start();
    }

    @Override
    public Flux<POI> searchByCategory(String city, String district, String category) {
        var cacheKey = city + ":" + district + ":" + category;
        var cached = cache.get(cacheKey);
        if (cached != null) {
            log.debug("Cache hit for {}", cacheKey);
            return Flux.fromIterable(cached);
        }

        log.info("Calling Meituan API: searchByCategory city={}, district={}, category={}", city, district, category);

        // Map our category to Dianping API category name
        String dianpingCategory = mapToDianpingCategory(category);
        String query = district != null ? district + " " + dianpingCategory : dianpingCategory;

        return callMeituanPoiSearch(city, query, 1, 30)
                .flatMapMany(response -> parsePoiResponse(response, city))
                .flatMap(pois -> pois.isEmpty() ? searchWithGaode(city, query) : Mono.just(pois))
                .doOnNext(pois -> cache.put(cacheKey, pois))
                .flatMap(Flux::fromIterable);
    }

    @Override
    public Flux<POI> searchByKeyword(String city, String district, String keyword) {
        var cacheKey = "kw:" + city + ":" + district + ":" + keyword;
        var cached = cache.get(cacheKey);
        if (cached != null) {
            return Flux.fromIterable(cached);
        }

        log.info("Calling Meituan API: searchByKeyword city={}, district={}, keyword={}", city, district, keyword);
        String query = district != null ? district + " " + keyword : keyword;

        return callMeituanPoiSearch(city, query, 1, 30)
                .flatMapMany(response -> parsePoiResponse(response, city))
                .flatMap(pois -> pois.isEmpty() ? searchWithGaode(city, query) : Mono.just(pois))
                .doOnNext(pois -> cache.put(cacheKey, pois))
                .flatMap(Flux::fromIterable);
    }

    @Override
    public Flux<POI> searchWithinBudget(String city, String district, double maxCost) {
        log.info("Calling Meituan API: searchWithinBudget city={}, district={}, maxCost={}", city, district, maxCost);

        // Search restaurants with average cost filter
        String query = district != null ? district + " 美食" : "美食";
        return callMeituanPoiSearch(city, query, 1, 30)
                .flatMapMany(response -> parsePoiResponse(response, city))
                .flatMap(pois -> pois.isEmpty() ? searchWithGaode(city, query) : Mono.just(pois))
                .flatMap(Flux::fromIterable)
                .filter(poi -> poi.avgCost() <= maxCost || poi.avgCost() == 0);
    }

    @Override
    public Mono<POI> findById(String id) {
        var cacheKey = "id:" + id;

        // Check cache
        for (var entry : cache.entrySet()) {
            var match = entry.getValue().stream().filter(p -> p.id().equals(id)).findFirst();
            if (match.isPresent()) {
                return Mono.just(match.get());
            }
        }

        log.info("Calling Meituan API: findById id={}", id);
        return callMeituanPoiDetail(id)
                .flatMap(response -> parsePoiDetail(response))
                .timeout(Duration.ofSeconds(3))
                .onErrorResume(e -> {
                    log.warn("Failed to fetch POI detail: {}", e.getMessage());
                    return Mono.empty();
                });
    }

    @Override
    public Flux<POI> getAllByCity(String city) {
        var cacheKey = "city:" + city;
        var cached = cache.get(cacheKey);
        if (cached != null) {
            return Flux.fromIterable(cached);
        }

        log.info("Calling Meituan API: getAllByCity city={}", city);

        // Search multiple categories in parallel with Gaode fallback
        var categories = List.of("美食", "购物", "景点", "娱乐", "文化");
        var poifFlux = Flux.merge(categories.stream()
                .map(cat -> callMeituanPoiSearch(city, cat, 1, 20)
                        .flatMapMany(response -> parsePoiResponse(response, city))
                        .flatMap(pois -> pois.isEmpty() ? searchWithGaode(city, cat) : Mono.just(pois))
                        .flatMap(Flux::fromIterable))
                .toList())
                .distinct(POI::id)
                .collectList()
                .doOnNext(pois -> cache.put(cacheKey, pois));

        return poifFlux.flatMapMany(Flux::fromIterable);
    }

    @Override
    public Flux<POI> getByDistrict(String city, String district) {
        var cacheKey = "district:" + city + ":" + district;
        var cached = cache.get(cacheKey);
        if (cached != null) {
            return Flux.fromIterable(cached);
        }

        log.info("Calling Meituan API: getByDistrict city={}, district={}", city, district);

        return callMeituanPoiSearch(city, district, 1, 30)
                .flatMapMany(response -> parsePoiResponse(response, city))
                .flatMap(pois -> pois.isEmpty() ? searchWithGaode(city, district) : Mono.just(pois))
                .doOnNext(pois -> cache.put(cacheKey, pois))
                .flatMap(Flux::fromIterable);
    }

    @Override
    public List<String> getAvailableCities() {
        return List.of("北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "重庆", "西安");
    }

    @Override
    public List<String> getAvailableDistricts(String city) {
        return List.of(); // Return empty; API search handles this dynamically
    }

    // ──────────────────────────────────────────────
    // Meituan / Dianping API 调用
    // ──────────────────────────────────────────────

    /**
     * Call the Meituan Open Platform POI search API.
     * Endpoint: GET /api/v1/poi/search?city={city}&keyword={keyword}&page={page}&limit={limit}
     *
     * Falls back to Dianping API if Meituan endpoint fails.
     */
    private Mono<Map> callMeituanPoiSearch(String city, String keyword, int page, int limit) {
        log.debug("Meituan POI search: city={}, keyword={}", city, keyword);

        // Try Meituan Open Platform first
        return meituanClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/api/v1/poi/search")
                        .queryParam("city", city)
                        .queryParam("keyword", keyword)
                        .queryParam("page", page)
                        .queryParam("limit", Math.min(limit, 50))
                        .build())
                .retrieve()
                .bodyToMono(Map.class)
                .timeout(Duration.ofSeconds(3))
                .onErrorResume(WebClientResponseException.class, e -> {
                    log.warn("Meituan API error ({}), falling back to Dianping API: {}",
                            e.getStatusCode(), e.getMessage());
                    return callDianpingPoiSearch(city, keyword, page, limit);
                })
                .onErrorResume(e -> {
                    log.warn("Meituan API unavailable, falling back to Dianping API: {}", e.getMessage());
                    return callDianpingPoiSearch(city, keyword, page, limit);
                })
                .subscribeOn(Schedulers.boundedElastic());
    }

    /**
     * Fallback: call Dianping Open API.
     * Endpoint: GET /business/find?city={city}&keyword={keyword}&page={page}
     */
    private Mono<Map> callDianpingPoiSearch(String city, String keyword, int page, int limit) {
        log.info("Dianping API POI search: city={}, keyword={}", city, keyword);

        return dianpingClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/business/find")
                        .queryParam("city", city)
                        .queryParam("keyword", keyword)
                        .queryParam("page", page)
                        .queryParam("limit", limit)
                        .build())
                .retrieve()
                .bodyToMono(Map.class)
                .timeout(Duration.ofSeconds(3))
                .onErrorResume(e -> {
                    log.error("Dianping API also unavailable: {}", e.getMessage());
                    return Mono.just(Map.of("status", "error", "msg", e.getMessage()));
                })
                .subscribeOn(Schedulers.boundedElastic());
    }

    /**
     * Call Meituan POI detail API.
     * Endpoint: GET /api/v1/poi/detail?id={poiId}
     */
    private Mono<Map> callMeituanPoiDetail(String poiId) {
        return meituanClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/api/v1/poi/detail")
                        .queryParam("id", poiId)
                        .build())
                .retrieve()
                .bodyToMono(Map.class)
                .timeout(Duration.ofSeconds(3))
                .onErrorResume(e -> {
                    log.warn("Meituan POI detail API error: {}", e.getMessage());
                    return Mono.just(Map.of("status", "error", "msg", e.getMessage()));
                });
    }

    // ──────────────────────────────────────────────
    // 响应解析 — 将 Meituan/Dianping API 响应转为 POI 对象
    // ──────────────────────────────────────────────

    /**
     * Parse a Meituan/Dianping API search response into a list of POIs.
     */
    @SuppressWarnings("unchecked")
    private Mono<List<POI>> parsePoiResponse(Map response, String city) {
        try {
            var data = response.get("data");
            List<Map<String, Object>> items;

            if (data instanceof List) {
                items = (List<Map<String, Object>>) data;
            } else if (data instanceof Map map) {
                var list = map.get("list");
                var results = map.get("results");
                var pois = map.get("pois");
                if (list instanceof List) items = (List<Map<String, Object>>) list;
                else if (results instanceof List) items = (List<Map<String, Object>>) results;
                else if (pois instanceof List) items = (List<Map<String, Object>>) pois;
                else items = List.of();
            } else {
                items = List.of();
            }

            var pois = items.stream()
                    .map(item -> mapToPOI(item, city))
                    .filter(p -> p != null)
                    .toList();

            log.info("Parsed {} POIs from API response for city={}", pois.size(), city);
            return Mono.just(pois);
        } catch (Exception e) {
            log.warn("Failed to parse POI response: {}", e.getMessage());
            return Mono.just(List.of());
        }
    }

    /**
     * Parse a single POI detail response.
     */
    @SuppressWarnings("unchecked")
    private Mono<POI> parsePoiDetail(Map response) {
        try {
            var data = response.get("data");
            if (data instanceof Map map) {
                return Mono.justOrEmpty(mapToPOI((Map<String, Object>) map, ""));
            }
            return Mono.empty();
        } catch (Exception e) {
            log.warn("Failed to parse POI detail: {}", e.getMessage());
            return Mono.empty();
        }
    }

    /**
     * Map a Meituan/Dianping API business object to our POI record.
     * Handles different API response formats flexibly.
     */
    @SuppressWarnings("unchecked")
    private POI mapToPOI(Map<String, Object> item, String defaultCity) {
        try {
            var id = strVal(item, "id", "poi_id", "business_id", "shop_id", "uuid");
            var name = strVal(item, "name", "shop_name", "business_name", "title", "poi_name");
            var address = strVal(item, "address", "shop_address", "addr", "business_address");
            var lat = doubleVal(item, "lat", "latitude", "lat_lng.lat");
            var lng = doubleVal(item, "lng", "longitude", "lat_lng.lng");

            if (id == null || name == null) return null;

            var city = strVal(item, "city", "city_name") != null
                    ? strVal(item, "city", "city_name") : defaultCity;
            var district = strVal(item, "district", "area", "region", "district_name");
            var rating = doubleVal(item, "avg_score", "rating", "score", "star", "review_score");
            var avgCost = doubleVal(item, "avg_price", "price", "avg_cost", "per_price", "average_cost");
            var categoryName = strVal(item, "category_name", "category", "cate", "type", "business_type");
            var subCategory = strVal(item, "sub_category", "sub_cate", "subcategory");
            var openTimeStr = strVal(item, "open_time", "opening_hours", "business_hours", "hours");
            var closeTimeStr = strVal(item, "close_time", "closing_hours");
            var queueTime = doubleVal(item, "queue_time", "wait_time", "avg_queue");
            var tagsRaw = item.get("tags");
            var description = strVal(item, "description", "intro", "recommend", "feature", "notice");
            var imageUrl = strVal(item, "image_url", "cover_img", "photo", "img_url", "shop_photo");

            List<String> tags = List.of();
            if (tagsRaw instanceof List tagList) {
                tags = tagList.stream().map(Object::toString).toList();
            } else if (tagsRaw instanceof String tagStr) {
                tags = List.of(tagStr.split("[,\\s;；、，]+"));
            }

            // Derive tags from category and rating
            var tagBuilder = new java.util.ArrayList<>(tags);
            if (rating >= 4.5) tagBuilder.add("高分");
            if (avgCost >= 300) tagBuilder.add("高端");
            if (avgCost > 0 && avgCost < 80) tagBuilder.add("平价");
            if (queueTime > 20) tagBuilder.add("排队");

            var poiId = "api_" + id;
            var category = mapCategory(categoryName);
            LocalTime openTime = parseTime(openTimeStr, "08:00");
            LocalTime closeTime = parseTime(closeTimeStr, "22:00");
            int visitDuration = estimateVisitDuration(category);
            double popularity = rating * 20 - avgCost * 0.05;

            return new POI(
                    poiId, name, category, subCategory != null ? subCategory : categoryName,
                    lat, lng, address != null ? address : "",
                    district != null ? district : "", city,
                    rating, Math.max(0, avgCost), Math.max(0, queueTime),
                    openTime, closeTime, visitDuration,
                    List.copyOf(tagBuilder), imageUrl != null ? imageUrl : "",
                    description != null ? description : "",
                    Math.max(0, Math.min(100, popularity))
            );
        } catch (Exception e) {
            log.warn("Failed to map POI from API item: {}", e.getMessage());
            return null;
        }
    }

    /**
     * Fallback to Gaode POI search when Dianping APIs are unavailable.
     */
    @SuppressWarnings("unchecked")
    private Mono<List<POI>> searchWithGaode(String city, String keyword) {
        log.info("Falling back to Gaode POI search: city={}, keyword={}", city, keyword);
        // Use Beijing center coordinates as default
        double lng = 116.3972;
        double lat = 39.9163;

        return gaodeGeoService.searchNearby(keyword, null, city, lng, lat, 20000)
                .map(gaodeResults -> {
                    List<POI> pois = new ArrayList<>();
                    for (var item : gaodeResults) {
                        try {
                            var id = String.valueOf(item.getOrDefault("id", "gaode_" + pois.size()));
                            var name = String.valueOf(item.getOrDefault("name", ""));
                            var address = String.valueOf(item.getOrDefault("address", ""));
                            var location = String.valueOf(item.getOrDefault("location", "0,0"));
                            var lngLat = location.split(",");
                            double pLng = lngLat.length >= 1 ? Double.parseDouble(lngLat[0]) : lng;
                            double pLat = lngLat.length >= 2 ? Double.parseDouble(lngLat[1]) : lat;
                            var type = String.valueOf(item.getOrDefault("type", ""));
                            var bizType = String.valueOf(item.getOrDefault("biz_type", ""));
                            var bizExt = (Map<String, Object>) item.get("biz_ext");
                            double rating = 0;
                            double avgCost = 0;
                            if (bizExt != null) {
                                try { rating = Double.parseDouble(String.valueOf(bizExt.getOrDefault("rating", "0"))); } catch (Exception ignored) {}
                                try { avgCost = Double.parseDouble(String.valueOf(bizExt.getOrDefault("cost", "0"))); } catch (Exception ignored) {}
                            }

                            var category = mapCategory(type.isEmpty() ? bizType : type);
                            var dist = String.valueOf(item.getOrDefault("distance", ""));
                            var distVal = 0;
                            if (!dist.isEmpty() && !"[]".equals(dist)) {
                                try { distVal = Integer.parseInt(dist); } catch (Exception ignored) {}
                            }

                            pois.add(new POI(
                                    "gaode_" + id, name, category, type,
                                    pLat, pLng, address, "", city,
                                    rating, avgCost, 0,
                                    LocalTime.of(8, 0), LocalTime.of(22, 0),
                                    estimateVisitDuration(category),
                                    List.of(), "", "", 50.0
                            ));
                        } catch (Exception e) {
                            // skip malformed Gaode result
                        }
                    }
                    log.info("Gaode fallback returned {} POIs for keyword={}", pois.size(), keyword);
                    return pois;
                })
                .onErrorResume(e -> {
                    log.warn("Gaode fallback also failed: {}", e.getMessage());
                    return Mono.just(List.<POI>of());
                });
    }

    // ──────────────────────────────────────────────
    // 工具方法
    // ──────────────────────────────────────────────

    private String strVal(Map<String, Object> map, String... keys) {
        for (var key : keys) {
            // Support dot notation for nested keys
            if (key.contains(".")) {
                var parts = key.split("\\.");
                Object current = map;
                for (var part : parts) {
                    if (current instanceof Map m) {
                        current = m.get(part);
                    } else {
                        current = null;
                        break;
                    }
                }
                if (current instanceof String s && !s.isBlank()) return s;
                if (current != null) return current.toString();
            }

            var val = map.get(key);
            if (val instanceof String s && !s.isBlank()) return s;
            if (val instanceof Number) return val.toString();
        }
        return null;
    }

    private double doubleVal(Map<String, Object> map, String... keys) {
        for (var key : keys) {
            if (key.contains(".")) {
                var parts = key.split("\\.");
                Object current = map;
                for (var part : parts) {
                    if (current instanceof Map m) {
                        current = m.get(part);
                    } else {
                        current = null;
                        break;
                    }
                }
                if (current instanceof Number n) return n.doubleValue();
                if (current instanceof String s) {
                    try { return Double.parseDouble(s); } catch (Exception ignored) {}
                }
            }

            var val = map.get(key);
            if (val instanceof Number n) return n.doubleValue();
            if (val instanceof String s) {
                try { return Double.parseDouble(s.replaceAll("[¥￥$￥,，]", "")); } catch (Exception ignored) {}
            }
        }
        return 0.0;
    }

    private String mapCategory(String dianpingCategory) {
        if (dianpingCategory == null) return "ATTRACTION";
        for (var entry : CATEGORY_MAP.entrySet()) {
            if (dianpingCategory.contains(entry.getKey())) {
                return entry.getValue();
            }
        }
        // Heuristic mapping
        if (dianpingCategory.contains("餐") || dianpingCategory.contains("吃")
                || dianpingCategory.contains("饮") || dianpingCategory.contains("咖啡")) return "RESTAURANT";
        if (dianpingCategory.contains("购") || dianpingCategory.contains("商")) return "SHOPPING";
        if (dianpingCategory.contains("景") || dianpingCategory.contains("公园")
                || dianpingCategory.contains("游")) return "ATTRACTION";
        if (dianpingCategory.contains("娱") || dianpingCategory.contains("影")
                || dianpingCategory.contains("吧")) return "ENTERTAINMENT";
        if (dianpingCategory.contains("化") || dianpingCategory.contains("博")
                || dianpingCategory.contains("书") || dianpingCategory.contains("展")) return "CULTURE";
        return "ATTRACTION";
    }

    private String mapToDianpingCategory(String ourCategory) {
        return switch (ourCategory) {
            case "RESTAURANT" -> "美食";
            case "SHOPPING" -> "购物";
            case "ATTRACTION" -> "景点";
            case "ENTERTAINMENT" -> "娱乐";
            case "CULTURE" -> "文化";
            default -> "美食";
        };
    }

    private LocalTime parseTime(String timeStr, String defaultTime) {
        if (timeStr == null || timeStr.isBlank()) return LocalTime.parse(defaultTime);
        try {
            // Handle various formats: "08:00-22:00", "8:00", "8:00am", etc.
            var clean = timeStr.trim()
                    .replaceAll("[-–—~～至到].*", "")
                    .replaceAll("[上下早中晚夜零一二三四五六七八九十]+", "")
                    .trim();
            if (clean.length() >= 5 && clean.contains(":")) {
                return LocalTime.parse(clean.substring(0, 5));
            }
            if (clean.matches("\\d{1,2}:\\d{2}")) {
                return LocalTime.parse(clean.length() == 4 ? "0" + clean : clean);
            }
        } catch (Exception ignored) {}
        return LocalTime.parse(defaultTime);
    }

    private int estimateVisitDuration(String category) {
        return switch (category) {
            case "RESTAURANT" -> 75;
            case "SHOPPING" -> 90;
            case "ATTRACTION" -> 120;
            case "ENTERTAINMENT" -> 120;
            case "CULTURE" -> 90;
            default -> 60;
        };
    }
}
