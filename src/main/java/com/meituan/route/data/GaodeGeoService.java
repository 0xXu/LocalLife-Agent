package com.meituan.route.data;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

import java.math.BigInteger;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Gaode Maps Web Service API — geocoding and reverse geocoding.
 * Uses AMap REST API (restapi.amap.com) to convert addresses to coordinates and vice versa.
 */
@Service
public class GaodeGeoService {

    private static final Logger log = LoggerFactory.getLogger(GaodeGeoService.class);

    private final WebClient client;
    private final String apiKey;
    private final String securityKey;
    private final ToolHarness harness;

    public GaodeGeoService(
            WebClient.Builder builder,
            @Value("${gaode.api.key}") String apiKey,
            @Value("${gaode.api.security-key:}") String securityKey,
            @Value("${gaode.api.base-url}") String baseUrl) {
        this.apiKey = apiKey;
        this.securityKey = securityKey;
        this.client = builder
                .baseUrl(baseUrl)
                .build();
        this.harness = new ToolHarness();
        log.info("GaodeGeoService initialized: baseUrl={}, securityKey={}", baseUrl,
                securityKey != null && !securityKey.isEmpty() ? "***" : "none");
    }

    /**
     * Geocode an address string to a [lng, lat] pair.
     */
    @SuppressWarnings("unchecked")
    public Mono<double[]> geocode(String address, String city) {
        String cacheKey = "geocode_" + (city != null ? city : "beijing") + "_" + address.hashCode();
        return harness.execute(() -> {
            var params = new TreeMap<String, String>();
            params.put("key", apiKey());
            params.put("address", address);
            params.put("city", city != null ? city : "北京");
            params.put("output", "json");

            return client.get()
                    .uri(signUri("/v3/geocode/geo", params))
                    .retrieve()
                    .bodyToMono(Map.class)
                    .flatMap(response -> {
                        try {
                            var status = String.valueOf(response.getOrDefault("status", "0"));
                            if (!"1".equals(status)) return Mono.empty();
                            var geocodes = (List<Map<String, Object>>) response.get("geocodes");
                            if (geocodes == null || geocodes.isEmpty()) return Mono.empty();
                            var loc = String.valueOf(geocodes.get(0).get("location"));
                            var parts = loc.split(",");
                            if (parts.length == 2) {
                                return Mono.just(new double[]{Double.parseDouble(parts[0]), Double.parseDouble(parts[1])});
                            }
                            return Mono.empty();
                        } catch (Exception e) { return Mono.empty(); }
                    });
        }, cacheKey);
    }

    /**
     * Reverse geocode: convert [lng, lat] to an address string.
     */
    @SuppressWarnings("unchecked")
    public Mono<String> reverseGeocode(double lng, double lat) {
        String cacheKey = "regeo_" + Math.round(lng * 1000) + "_" + Math.round(lat * 1000);
        return harness.execute(() -> {
            var params = new TreeMap<String, String>();
            params.put("key", apiKey());
            params.put("location", lng + "," + lat);
            params.put("output", "json");
            return client.get()
                    .uri(signUri("/v3/geocode/regeo", params))
                    .retrieve()
                    .bodyToMono(Map.class)
                    .flatMap(response -> {
                        var status = String.valueOf(response.getOrDefault("status", "0"));
                        if (!"1".equals(status)) return Mono.empty();
                        var regeocode = (Map<String, Object>) response.get("regeocode");
                        return Mono.justOrEmpty(regeocode != null ? String.valueOf(regeocode.getOrDefault("formatted_address", "")) : null);
                    });
        }, cacheKey);
    }

    /**
     * Search POIs near a location using Gaode POI search API.
     */
    @SuppressWarnings("unchecked")
    public Mono<List<Map<String, Object>>> searchNearby(
            String keywords, String types, String city, double lng, double lat, int radius) {
        String cacheKey = "poi_" + (city != null ? city : "") + "_" +
                (keywords != null ? keywords.hashCode() : "") + "_" + Math.round(lng * 100) + "_" + Math.round(lat * 100);
        return harness.execute(() -> {
            var params = new TreeMap<String, String>();
            params.put("key", apiKey());
            params.put("location", lng + "," + lat);
            params.put("radius", String.valueOf(radius));
            params.put("output", "json");
            params.put("offset", "25");
            if (keywords != null && !keywords.isBlank()) params.put("keywords", keywords);
            if (types != null && !types.isBlank()) params.put("types", types);
            if (city != null && !city.isBlank()) params.put("city", city);

            return client.get()
                    .uri(signUri("/v3/place/around", params))
                    .retrieve()
                    .bodyToMono(Map.class)
                    .flatMap(response -> {
                        var status = String.valueOf(response.getOrDefault("status", "0"));
                        if (!"1".equals(status)) return Mono.just(List.<Map<String, Object>>of());
                        var pois = (List<Map<String, Object>>) response.get("pois");
                        return Mono.just(pois != null ? pois : List.<Map<String, Object>>of());
                    });
        }, cacheKey, List.of());
    }

    // ─── AMap signature ──────────────────────────────────────────

    /**
     * Build a signed URI string. AMap requires sorted params + MD5(concat + securityKey).
     */
    private String signUri(String path, TreeMap<String, String> params) {
        var sb = new StringBuilder();
        for (var e : params.entrySet()) {
            if (!sb.isEmpty()) sb.append("&");
            sb.append(e.getKey()).append("=").append(e.getValue());
        }
        if (securityKey != null && !securityKey.isEmpty()) {
            String sig = md5(sb.toString() + securityKey);
            sb.append("&sig=").append(sig);
        }
        return path + "?" + sb.toString();
    }

    private String md5(String input) {
        try {
            var md = MessageDigest.getInstance("MD5");
            byte[] digest = md.digest(input.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            // Pad to 32 hex chars — BigInteger drops leading zeros
            return String.format("%032x", new BigInteger(1, digest));
        } catch (Exception e) {
            return "";
        }
    }

    /**
     * Calculate driving distance and duration between two points using AMap Distance API.
     * Returns [distance_km, duration_minutes] or null on failure.
     */
    @SuppressWarnings("unchecked")
    public Mono<double[]> getDrivingDistance(double fromLng, double fromLat, double toLng, double toLat) {
        String cacheKey = "dist_" + Math.round(fromLng * 1000) + "_" + Math.round(fromLat * 1000) +
                "_" + Math.round(toLng * 1000) + "_" + Math.round(toLat * 1000);
        return harness.execute(() -> {
            var params = new TreeMap<String, String>();
            params.put("key", apiKey());
            params.put("origins", fromLng + "," + fromLat);
            params.put("destination", toLng + "," + toLat);
            params.put("type", "0");
            return client.get()
                    .uri(signUri("/v3/distance", params))
                    .retrieve()
                    .bodyToMono(Map.class)
                    .flatMap(response -> {
                        var status = String.valueOf(response.getOrDefault("status", "0"));
                        if (!"1".equals(status)) return Mono.empty();
                        var results = (List<Map<String, Object>>) response.get("results");
                        if (results == null || results.isEmpty()) return Mono.empty();
                        var distStr = String.valueOf(results.get(0).getOrDefault("distance", "0"));
                        var durStr = String.valueOf(results.get(0).getOrDefault("duration", "0"));
                        return Mono.just(new double[]{Double.parseDouble(distStr) / 1000.0, Double.parseDouble(durStr) / 60.0});
                    });
        }, cacheKey);
    }

    /**
     * Batch driving distance calculation for multiple origin-destination pairs.
     * Uses AMap Distance Matrix API. Returns map of "fromId-toId" -> [distanceKm, durationMin].
     */
    @SuppressWarnings("unchecked")
    public Mono<Map<String, double[]>> getDistanceMatrixBatch(
            List<double[]> origins, List<double[]> destinations) {
        if (origins.isEmpty() || destinations.isEmpty()) return Mono.just(Map.of());

        var originsStr = new StringBuilder();
        for (int i = 0; i < Math.min(origins.size(), 10); i++) {
            if (i > 0) originsStr.append("|");
            originsStr.append(origins.get(i)[0]).append(",").append(origins.get(i)[1]);
        }
        var destStr = new StringBuilder();
        for (int i = 0; i < Math.min(destinations.size(), 10); i++) {
            if (i > 0) destStr.append("|");
            destStr.append(destinations.get(i)[0]).append(",").append(destinations.get(i)[1]);
        }

        String cacheKey = "distBatch_" + originsStr.toString().hashCode() + "_" + destStr.toString().hashCode();
        return harness.execute(() -> {
            var params = new TreeMap<String, String>();
            params.put("key", apiKey());
            params.put("origins", originsStr.toString());
            params.put("destination", destStr.toString());
            params.put("type", "0");
            return client.get()
                    .uri(signUri("/v3/distance", params))
                    .retrieve()
                    .bodyToMono(Map.class)
                    .flatMap(response -> {
                        var status = String.valueOf(response.getOrDefault("status", "0"));
                        if (!"1".equals(status)) return Mono.just(Map.<String, double[]>of());
                        var results = (List<Map<String, Object>>) response.get("results");
                        if (results == null) return Mono.just(Map.<String, double[]>of());
                        Map<String, double[]> matrix = new java.util.LinkedHashMap<>();
                        for (int i = 0; i < results.size(); i++) {
                            var result = results.get(i);
                            try {
                                double d = Double.parseDouble(String.valueOf(result.getOrDefault("distance", "0"))) / 1000.0;
                                double t = Double.parseDouble(String.valueOf(result.getOrDefault("duration", "0"))) / 60.0;
                                matrix.put(String.valueOf(i), new double[]{d, t});
                            } catch (NumberFormatException ignored) {}
                        }
                        return Mono.just(matrix);
                    });
        }, cacheKey, Map.of());
    }

    private String apiKey() {
        return apiKey;
    }
}
