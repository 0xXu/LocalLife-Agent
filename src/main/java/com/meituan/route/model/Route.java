package com.meituan.route.model;

import java.time.LocalTime;
import java.util.List;

/**
 * A complete route plan consisting of ordered POI visits with timing.
 */
public record Route(
        String id,
        String name,
        String description,
        List<RouteSegment> segments,
        double totalCost,
        double totalTravelTime,   // minutes
        double totalRating,
        String optimizationGoal,  // BEST_EXPERIENCE, FASTEST, CHEAPEST
        List<Constraint> satisfiedConstraints,
        List<Constraint> violatedSoftConstraints,
        double score              // composite score for ranking
) {
    public record RouteSegment(
            POI poi,
            LocalTime arrivalTime,
            LocalTime departureTime,
            double travelTimeFromPrevious, // minutes; 0 for first POI
            String travelMode              // WALKING, DRIVING
    ) {
        public double duration() {
            return java.time.Duration.between(arrivalTime, departureTime).toMinutes();
        }
    }
}
