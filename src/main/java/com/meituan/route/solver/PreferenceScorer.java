package com.meituan.route.solver;

import com.meituan.route.model.POI;
import com.meituan.route.model.Route;
import com.meituan.route.model.UserPreference;
import org.springframework.stereotype.Component;

import java.util.*;

/**
 * Computes preference-match scores for POIs and routes against a user profile.
 * Algorithm: score = sum(matched preference_tag weights) - sum(matched avoid_tag weights)
 *
 * UGC tags (from real user reviews) carry 1.5× the weight of merchant-provided tags,
 * because they represent authentic, crowdsourced feedback rather than self-reported attributes.
 */
@Component
public class PreferenceScorer {

    /** Multiplier applied when a preference/avoidance is matched via UGC tags vs merchant tags. */
    private static final double UGC_WEIGHT_MULTIPLIER = 1.5;

    /**
     * Score a single POI against a user's preference profile.
     * Positive = matches preferences, negative = matches avoidances.
     * Matching via UGC tags (real user reviews) gets a 1.5× bonus.
     */
    public double scorePOI(POI poi, UserPreference profile) {
        if (profile == null || poi == null) return 0;
        var poiTags = poi.tags();
        var poiUGCTags = poi.ugcTags();
        var poiRiskTags = poi.riskTags();
        if ((poiTags == null || poiTags.isEmpty()) && (poiUGCTags == null || poiUGCTags.isEmpty())) return 0;

        double score = 0;
        for (var entry : profile.preferenceTags().entrySet()) {
            if (tagMatches(poiTags, entry.getKey())) {
                score += entry.getValue();
            } else if (tagMatches(poiUGCTags, entry.getKey())) {
                // UGC match carries higher weight — real user feedback
                score += entry.getValue() * UGC_WEIGHT_MULTIPLIER;
            }
        }
        for (var entry : profile.avoidTags().entrySet()) {
            if (tagMatches(poiTags, entry.getKey())) {
                score -= entry.getValue();
            } else if (tagMatches(poiUGCTags, entry.getKey())) {
                // UGC avoid match penalized more heavily
                score -= entry.getValue() * UGC_WEIGHT_MULTIPLIER;
            }
            // Risk tags also trigger avoidance penalty (at UGC weight level)
            if (tagMatches(poiRiskTags, entry.getKey())) {
                score -= entry.getValue() * UGC_WEIGHT_MULTIPLIER;
            }
        }
        return score;
    }

    /**
     * Score a POI using ONLY UGC tags — returns 0 if no UGC data exists.
     * Used for the "UGC override" logic: when UGC contradicts merchant tags,
     * UGC opinion takes precedence.
     */
    public double scorePOIByUGCOnly(POI poi, UserPreference profile) {
        if (profile == null || poi == null || !poi.hasUGC()) return 0;
        var ugcTags = poi.ugcTags();
        double score = 0;
        for (var entry : profile.preferenceTags().entrySet()) {
            if (tagMatches(ugcTags, entry.getKey())) {
                score += entry.getValue() * UGC_WEIGHT_MULTIPLIER;
            }
        }
        for (var entry : profile.avoidTags().entrySet()) {
            if (tagMatches(ugcTags, entry.getKey())) {
                score -= entry.getValue() * UGC_WEIGHT_MULTIPLIER;
            }
        }
        return score;
    }

    /**
     * Score a route as the average of all its POI preference scores.
     */
    public double scoreRoute(Route route, UserPreference profile) {
        if (route == null || route.segments() == null || route.segments().isEmpty()) return 0;
        return route.segments().stream()
                .mapToDouble(s -> scorePOI(s.poi(), profile))
                .average().orElse(0);
    }

    /**
     * Normalize raw preference score to 0-100 scale using a sigmoid function.
     */
    public double normalizedScore(Route route, UserPreference profile) {
        double raw = scoreRoute(route, profile);
        return 100.0 / (1.0 + Math.exp(-raw * 2.5));
    }

    /**
     * Get the top matched preference tags for display (up to 4).
     * Returns the preference tag names that matched POIs in the route (both merchant and UGC tags).
     */
    public List<String> matchedTags(Route route, UserPreference profile) {
        if (profile == null || route == null || route.segments() == null) return List.of();
        Set<String> allPoiTags = new HashSet<>();
        for (var seg : route.segments()) {
            var tags = seg.poi().tags();
            if (tags != null) allPoiTags.addAll(tags);
            var ugcTags = seg.poi().ugcTags();
            if (ugcTags != null) allPoiTags.addAll(ugcTags);
        }
        return profile.preferenceTags().keySet().stream()
                .filter(tag -> allPoiTags.stream().anyMatch(pt -> tagMatches(List.of(pt), tag)))
                .sorted((a, b) -> Double.compare(
                        profile.preferenceTags().getOrDefault(b, 0.0),
                        profile.preferenceTags().getOrDefault(a, 0.0)))
                .limit(4)
                .toList();
    }

    /**
     * Get tags that were matched specifically from UGC reviews (not merchant tags).
     * These are shown to the user as "来自真实评价: xxx" to build trust.
     */
    public List<String> matchedUGCTags(Route route, UserPreference profile) {
        if (profile == null || route == null || route.segments() == null) return List.of();
        Set<String> allPoiTags = new HashSet<>();
        Set<String> allUGCTags = new HashSet<>();
        for (var seg : route.segments()) {
            var tags = seg.poi().tags();
            if (tags != null) allPoiTags.addAll(tags);
            var ugcTags = seg.poi().ugcTags();
            if (ugcTags != null) allUGCTags.addAll(ugcTags);
        }
        // Only return tags matched from UGC, NOT from merchant tags
        return profile.preferenceTags().keySet().stream()
                .filter(tag -> !allPoiTags.stream().anyMatch(pt -> tagMatches(List.of(pt), tag))
                        && allUGCTags.stream().anyMatch(ut -> tagMatches(List.of(ut), tag)))
                .limit(3)
                .toList();
    }

    /**
     * Get the UGC summary snippets that match user preferences across the route.
     * Returns up to 3 UGC summaries for POIs that positively match the user profile.
     */
    public List<String> matchedUGCSummaries(Route route, UserPreference profile) {
        if (profile == null || route == null || route.segments() == null) return List.of();
        var summaries = new ArrayList<String>();
        for (var seg : route.segments()) {
            var poi = seg.poi();
            if (!poi.hasUGC()) continue;
            double ugcScore = scorePOIByUGCOnly(poi, profile);
            if (ugcScore > 0 && !poi.ugcSummary().isBlank()) {
                summaries.add(poi.name() + "：" + poi.ugcSummary());
            }
        }
        return summaries.subList(0, Math.min(3, summaries.size()));
    }

    /**
     * Combined route score: 50% constraint satisfaction + 50% preference match.
     */
    public double combinedScore(Route route, UserPreference profile) {
        double prefNorm = normalizedScore(route, profile);
        double existingScore = route.score();
        return existingScore * 0.5 + prefNorm * 0.5;
    }

    private boolean tagMatches(List<String> poiTags, String profileTag) {
        for (var pt : poiTags) {
            if (pt.contains(profileTag) || profileTag.contains(pt)) return true;
        }
        return false;
    }
}
