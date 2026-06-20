package com.meituan.route.agent;

import com.meituan.route.data.DataService;
import com.meituan.route.model.POI;
import com.meituan.route.model.UserIntent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.time.LocalTime;
import java.util.*;
import java.util.stream.Collectors;

/**
 * DiscoveryAgent receives a UserIntent and retrieves candidate POIs from the DataService.
 * Applies hard constraint filtering (time, category matching).
 */
@Component
public class DiscoveryAgent {

    private static final Logger log = LoggerFactory.getLogger(DiscoveryAgent.class);

    private final DataService dataService;

    public DiscoveryAgent(DataService dataService) {
        this.dataService = dataService;
    }

    /**
     * Discover candidate POIs based on user intent.
     * Uses parallel queries for different categories.
     */
    public Mono<DiscoveryResult> discover(UserIntent intent) {
        log.info("DiscoveryAgent searching for POIs in {} {} categories: {}",
                intent.city(), intent.district(), intent.preferredCategories());

        String city = intent.city() != null ? intent.city() : "北京";

        // If specific categories are provided, search by each in parallel
        List<String> categories = intent.preferredCategories();
        boolean hasKeywords = intent.keywords() != null && !intent.keywords().isEmpty();
        if (categories == null || categories.isEmpty()) {
            // When keywords are present, limit to food/drink/entertainment —
            // searching all 5 categories would dilute results with attractions
            // that have higher ratings but are irrelevant to keyword-based queries.
            if (hasKeywords) {
                categories = new ArrayList<>(List.of("RESTAURANT", "ENTERTAINMENT"));
            } else {
                categories = new ArrayList<>(List.of("RESTAURANT", "ATTRACTION", "SHOPPING", "ENTERTAINMENT", "CULTURE"));
            }
        } else {
            // Ensure mutable so we can expand below
            categories = new ArrayList<>(categories);
        }
        // Expand categories for mixed-activity queries: 逛逛/逛街 + 吃饭/咖啡
        // so users get multi-POI routes (TC02, TC08). Apply regardless of whether
        // LLM parsed categories or we used defaults.
        expandCategoriesForMixedActivity(categories, intent);

        // Parallel search across categories
        var poiFluxes = new ArrayList<>(categories.stream()
                .map(cat -> dataService.searchByCategory(city, intent.district(), cat))
                .toList());

        // Keyword-based search for named POIs
        if (intent.keywords() != null && !intent.keywords().isEmpty()) {
            for (var kw : intent.keywords()) {
                poiFluxes.add(dataService.searchByKeyword(city, intent.district(), kw));
            }
        }

        var allPOIs = Flux.merge(poiFluxes)
                .distinct(POI::id)
                .collectList()
                .flatMap(pois -> {
                    var hasSpecific = intent.preferredCategories() != null && !intent.preferredCategories().isEmpty();
                    if (pois.isEmpty() && (hasSpecific || hasKeywords)) {
                        // No POIs found — fall back progressively:
                        // 1) keywords only (most relevant to user intent)
                        // 2) RESTAURANT only (food/drink usually want restaurants)
                        // 3) RESTAURANT + ATTRACTION (broad last resort)
                        log.info("DiscoveryAgent: no POIs for {}, trying keyword-first fallback",
                                intent.preferredCategories());
                        if (hasKeywords) {
                            var kwFluxes = intent.keywords().stream()
                                    .map(kw -> dataService.searchByKeyword(city, intent.district(), kw))
                                    .toList();
                            return Flux.merge(kwFluxes)
                                    .distinct(POI::id)
                                    .collectList()
                                    .flatMap(kwPois -> {
                                        if (!kwPois.isEmpty()) return applyHardFilters(kwPois, intent);
                                        // Keywords also empty — try RESTAURANT only
                                        log.info("DiscoveryAgent: keywords empty, trying RESTAURANT only");
                                        return dataService.searchByCategory(city, intent.district(), "RESTAURANT")
                                                .collectList()
                                                .flatMap(rPois -> {
                                                    if (!rPois.isEmpty()) return applyHardFilters(rPois, intent);
                                                    // Last resort: all categories
                                                    return broadFallback(city, intent);
                                                });
                                    });
                        }
                        return broadFallback(city, intent);
                    }
                    return applyHardFilters(pois, intent);
                });

        return allPOIs.map(pois -> {
            log.info("DiscoveryAgent found {} POIs after filtering", pois.size());
            return new DiscoveryResult(pois, categorizePOIs(pois), intent);
        });
    }

    /**
     * Apply hard constraints to filter candidates.
     */
    private Mono<List<POI>> applyHardFilters(List<POI> pois, UserIntent intent) {
        // Check if user wants drinks/bars
        var wantsDrinks = hasDrinkKeywords(intent);
        var filtered = pois.stream()
                .filter(poi -> {
                    if (intent.budget() > 0 && poi.avgCost() > intent.budget() * 2) {
                        return false;
                    }
                    return true;
                })
                .sorted((a, b) -> {
                    // Boost bar/drink POIs when user wants drinks
                    double scoreA = computeBoostScore(a, wantsDrinks);
                    double scoreB = computeBoostScore(b, wantsDrinks);
                    return Double.compare(scoreB, scoreA);
                })
                .limit(50) // More candidates for better coverage
                .toList();

        return Mono.just(filtered);
    }

    private boolean hasDrinkKeywords(UserIntent intent) {
        // Check keywords
        if (intent.keywords() != null) {
            var kwMatch = intent.keywords().stream().anyMatch(kw ->
                    kw.contains("酒") || kw.contains("喝") || kw.contains("吧") || kw.contains("精酿"));
            if (kwMatch) return true;
        }
        // Also check raw query text
        if (intent.rawQuery() != null) {
            var q = intent.rawQuery();
            return q.contains("酒") || q.contains("喝") || q.contains("吧") || q.contains("精酿");
        }
        return false;
    }

    private double computeBoostScore(POI poi, boolean wantsDrinks) {
        double base = poi.rating() * 10 + poi.popularityScore() * 0.2;
        if (wantsDrinks && isBarPOI(poi)) {
            base += 30; // significant boost for bar-related POIs
        }
        return base;
    }

    private boolean isBarPOI(POI poi) {
        if (poi.tags() == null) return false;
        return poi.tags().stream().anyMatch(t ->
                t.contains("酒") || t.contains("吧") || t.contains("精酿") || t.contains("居酒屋")
                || t.contains("小酌") || t.contains("深夜"));
    }

    /** Expand categories when query implies mixed activities (逛逛 + 吃饭 + 咖啡). */
    private void expandCategoriesForMixedActivity(List<String> categories, UserIntent intent) {
        var q = intent.rawQuery();
        if (q == null) return;
        boolean hasStroll = q.contains("逛") || q.contains("散步") || q.contains("走走")
                || q.contains("看展") || q.contains("逛街");
        boolean hasEat = q.contains("吃") || q.contains("饭") || q.contains("咖啡")
                || q.contains("喝") || q.contains("茶");
        if (hasStroll && hasEat) {
            if (!categories.contains("ATTRACTION")) categories.add("ATTRACTION");
            if (!categories.contains("SHOPPING")) categories.add("SHOPPING");
            if (!categories.contains("CULTURE")) categories.add("CULTURE");
            log.info("DiscoveryAgent: expanded categories for mixed activity → {}", categories);
        }
    }

    /** Last-resort fallback: search all available categories. */
    private Mono<List<POI>> broadFallback(String city, UserIntent intent) {
        log.info("DiscoveryAgent: broad fallback (RESTAURANT + ATTRACTION)");
        var fluxes = List.of("RESTAURANT", "ATTRACTION").stream()
                .map(cat -> dataService.searchByCategory(city, intent.district(), cat))
                .toList();
        return Flux.merge(fluxes)
                .distinct(POI::id)
                .collectList()
                .flatMap(pois -> applyHardFilters(pois, intent));
    }

    /**
     * Categorize POIs for easier processing by PlanningAgent.
     */
    private Map<String, List<POI>> categorizePOIs(List<POI> pois) {
        return pois.stream()
                .collect(Collectors.groupingBy(POI::category));
    }

    /**
     * Extract a user's special request keywords into POI tag filters.
     */
    public List<String> extractPreferenceTags(UserIntent intent) {
        var tags = new ArrayList<String>();
        if (intent.specialRequest() != null) {
            var req = intent.specialRequest();
            if (req.contains("拍照")) tags.add("拍照");
            if (req.contains("约会")) tags.add("约会");
            if (req.contains("安静")) tags.add("安静");
        }
        if (intent.keywords() != null) {
            tags.addAll(intent.keywords());
        }
        return tags;
    }

    /**
     * Create a broad intent for speculative discovery — search all categories
     * in the default city while LLM parses the real intent in parallel.
     */
    public static UserIntent broadIntent(String defaultCity) {
        return new UserIntent(
                "", defaultCity, null,
                null, // all categories
                null,
                java.time.LocalTime.of(14, 0), java.time.LocalTime.of(22, 0),
                0, 2, 3.5, 30,
                "WALKING", "BEST_EXPERIENCE",
                null, List.of(), null
        );
    }

    /**
     * Filter speculative discovery results to match the parsed intent's categories.
     * When speculative results already exist, this avoids a second API call.
     */
    public DiscoveryResult filterForIntent(DiscoveryResult speculative, UserIntent intent) {
        var targetCats = intent.preferredCategories();
        var hasCats = targetCats != null && !targetCats.isEmpty();
        var hasDistrict = intent.district() != null && !intent.district().isBlank();
        var hasKeywords = intent.keywords() != null && !intent.keywords().isEmpty();

        if (!hasCats && !hasDistrict && !hasKeywords) {
            return speculative;
        }

        var stream = speculative.candidates().stream();

        if (hasCats) {
            var targetSet = new java.util.HashSet<>(targetCats.stream()
                    .map(String::toUpperCase).toList());
            stream = stream.filter(poi -> {
                var cat = poi.category() != null ? poi.category().toUpperCase() : "";
                return targetSet.contains(cat) || targetSet.stream().anyMatch(cat::contains);
            });
        }

        if (hasDistrict) {
            stream = stream.filter(poi -> {
                if (poi.district().equals(intent.district())) return true;
                if (poi.name().contains(intent.district())) return true;
                if (poi.district().contains(intent.district()) || intent.district().contains(poi.district())) return true;
                if (poi.address() != null && poi.address().contains(intent.district())) return true;
                return false;
            });
        }

        if (hasKeywords) {
            stream = stream.filter(poi -> {
                for (var kw : intent.keywords()) {
                    if (poi.name().contains(kw)) return true;
                    if (poi.tags().stream().anyMatch(t -> t.contains(kw))) return true;
                    if (poi.description().contains(kw)) return true;
                }
                return false;
            });
        }

        var filtered = stream
                .sorted(java.util.Comparator.<POI, Double>comparing(p -> -p.rating())
                        .thenComparing(p -> -p.popularityScore()))
                .limit(50)
                .toList();

        log.info("DiscoveryAgent filtered speculative {} POIs → {} POIs (cats={}, district={}, keywords={})",
                speculative.candidates().size(), filtered.size(), hasCats, hasDistrict, hasKeywords);
        return new DiscoveryResult(filtered, categorizePOIs(filtered), intent);
    }

    public record DiscoveryResult(
            List<POI> candidates,
            Map<String, List<POI>> categorizedPOIs,
            UserIntent intent
    ) {}
}
