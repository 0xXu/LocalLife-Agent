package com.meituan.route.model;

import java.util.List;
import java.util.Map;

/**
 * User preference profile for personalized route scoring.
 * Decoupled from persistence — UserProfileService maps entities to this record.
 */
public record UserPreference(
        String userId,
        String name,
        String profileName,
        String preferredCity,
        double avgBudget,
        List<String> favoriteCategories,
        Map<String, Double> preferenceTags,
        Map<String, Double> avoidTags,
        List<String> historyActions
) {
    public static UserPreference neutral() {
        return new UserPreference("default", "游客", "默认模式",
                "北京", 0, List.of(), Map.of(), Map.of(), List.of());
    }
}
