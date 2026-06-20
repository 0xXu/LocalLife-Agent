package com.meituan.route.model;

import java.time.LocalTime;
import java.util.List;
import java.util.Optional;

/**
 * Structured user intent parsed from natural language.
 */
public record UserIntent(
        String rawQuery,
        String city,
        String district,
        List<String> preferredCategories,
        String cuisinePreference,
        LocalTime startTime,
        LocalTime endTime,
        double budget,
        int partySize,
        double minRating,
        int maxQueueMinutes,
        String travelMode,       // WALKING, DRIVING
        String optimizationGoal, // BEST_EXPERIENCE, FASTEST, CHEAPEST
        String specialRequest,   // e.g. "拍照好看", "少走路"
        List<String> keywords,
        String sessionId
) {
    // Validate and return missing fields
    public List<String> missingFields() {
        return List.of();
    }

    public Optional<String> OptimizationGoal() {
        return Optional.ofNullable(optimizationGoal);
    }

    public UserIntent withCity(String newCity) {
        return new UserIntent(rawQuery, newCity, district, preferredCategories,
                cuisinePreference, startTime, endTime, budget, partySize,
                minRating, maxQueueMinutes, travelMode, optimizationGoal,
                specialRequest, keywords, sessionId);
    }

    public UserIntent withGoal(String newGoal) {
        return new UserIntent(rawQuery, city, district, preferredCategories,
                cuisinePreference, startTime, endTime, budget, partySize,
                minRating, maxQueueMinutes, travelMode, newGoal,
                specialRequest, keywords, sessionId);
    }

    public UserIntent withTravelMode(String newTravelMode) {
        return new UserIntent(rawQuery, city, district, preferredCategories,
                cuisinePreference, startTime, endTime, budget, partySize,
                minRating, maxQueueMinutes, newTravelMode, optimizationGoal,
                specialRequest, keywords, sessionId);
    }

    public UserIntent withBudget(double newBudget) {
        return new UserIntent(rawQuery, city, district, preferredCategories,
                cuisinePreference, startTime, endTime, newBudget, partySize,
                minRating, maxQueueMinutes, travelMode, optimizationGoal,
                specialRequest, keywords, sessionId);
    }
}
