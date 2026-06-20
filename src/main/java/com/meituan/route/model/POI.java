package com.meituan.route.model;

import java.time.LocalTime;
import java.util.List;

/**
 * Point of Interest - a location that can be visited in a route.
 */
public record POI(
        String id,
        String name,
        String category,       // RESTAURANT, ATTRACTION, SHOPPING, ENTERTAINMENT, CULTURE
        String subCategory,
        double lat,
        double lng,
        String address,
        String district,       // e.g. "三里屯", "国贸"
        String city,
        double rating,
        double avgCost,
        double queueTime,      // estimated queue time in minutes
        LocalTime openTime,
        LocalTime closeTime,
        int visitDuration,     // recommended stay in minutes
        List<String> tags,
        String imageUrl,
        String description,
        double popularityScore, // 0-100
        List<String> ugcTags,   // tags extracted from real user reviews (UGC), e.g. "安静", "排队久"
        String ugcSummary,      // short summary of what users say, e.g. "人很多，排队久，环境吵"
        List<String> riskTags   // risk/warning tags, e.g. "排队久", "太吵", "环境嘈杂" (from UGC + merchant)
) {
    /** Compact constructor: ensure non-null defaults for UGC and risk fields. */
    public POI {
        if (ugcTags == null) ugcTags = List.of();
        if (ugcSummary == null) ugcSummary = "";
        if (riskTags == null) riskTags = List.of();
    }

    /** Backward-compatible constructor — all existing call sites without UGC/risk data. */
    public POI(String id, String name, String category, String subCategory,
               double lat, double lng, String address, String district, String city,
               double rating, double avgCost, double queueTime,
               LocalTime openTime, LocalTime closeTime, int visitDuration,
               List<String> tags, String imageUrl, String description,
               double popularityScore) {
        this(id, name, category, subCategory, lat, lng, address, district, city,
             rating, avgCost, queueTime, openTime, closeTime, visitDuration,
             tags, imageUrl, description, popularityScore, List.of(), "", List.of());
    }

    public boolean isOpenDuring(LocalTime start, LocalTime end) {
        return !start.isBefore(openTime) && !end.isAfter(closeTime);
    }

    public boolean matchesCategory(String cat) {
        return category.equalsIgnoreCase(cat) || tags.stream().anyMatch(t -> t.contains(cat));
    }

    /** Whether this POI has UGC review data. */
    public boolean hasUGC() {
        return !ugcTags.isEmpty() || !ugcSummary.isEmpty();
    }

    /** Return a copy with a different queueTime. */
    public POI withQueueTime(double newQueueTime) {
        return new POI(id, name, category, subCategory, lat, lng, address, district, city,
                rating, avgCost, newQueueTime, openTime, closeTime, visitDuration,
                tags, imageUrl, description, popularityScore, ugcTags, ugcSummary, riskTags);
    }

    /** Return a copy with UGC review data added. */
    public POI withUGC(List<String> newUgcTags, String newUgcSummary, List<String> newRiskTags) {
        return new POI(id, name, category, subCategory, lat, lng, address, district, city,
                rating, avgCost, queueTime, openTime, closeTime, visitDuration,
                tags, imageUrl, description, popularityScore, newUgcTags, newUgcSummary, newRiskTags);
    }
}
