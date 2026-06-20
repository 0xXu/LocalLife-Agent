package com.meituan.route.model;

import java.util.Optional;

/**
 * A constraint that a route must satisfy.
 */
public record Constraint(
        String id,
        ConstraintType type,
        Scope scope,
        double priority,        // higher = more important
        double weight,          // weight in scoring
        String description,
        Object value            // typed constraint value (parsed by engine)
) {
    public enum ConstraintType {
        HARD,   // must satisfy — pruning condition
        SOFT    // preference — scored
    }

    public enum Scope {
        GLOBAL,         // applies to whole route
        PER_POI,        // applies per individual POI
        ADJACENT_PAIR   // applies between consecutive POIs
    }

    @SuppressWarnings("unchecked")
    public <T> Optional<T> getValueAs(Class<T> clazz) {
        if (value != null && clazz.isInstance(value)) {
            return Optional.of((T) value);
        }
        return Optional.empty();
    }

    // Factory methods
    public static Constraint budget(double maxCost, double priority) {
        return new Constraint("budget", ConstraintType.SOFT, Scope.GLOBAL,
                priority, 0.3, "Budget limit: ¥" + maxCost, maxCost);
    }

    /** Budget as HARD constraint — routes exceeding this are rejected. */
    public static Constraint budgetHard(double maxCost) {
        return new Constraint("budget", ConstraintType.HARD, Scope.GLOBAL,
                9, 0.4, "Hard budget limit: ¥" + maxCost, maxCost);
    }

    public static Constraint timeWindow(String start, String end, double priority) {
        return new Constraint("time_window", ConstraintType.HARD, Scope.GLOBAL,
                priority, 0.0, "Time window: " + start + " - " + end,
                java.util.List.of(java.time.LocalTime.parse(start), java.time.LocalTime.parse(end)));
    }

    public static Constraint minRating(double minRating, double priority) {
        return new Constraint("min_rating", ConstraintType.SOFT, Scope.PER_POI,
                priority, 0.2, "Minimum rating: " + minRating, minRating);
    }

    public static Constraint category(String category, double priority) {
        return new Constraint("category", ConstraintType.HARD, Scope.PER_POI,
                priority, 0.0, "Category: " + category, category);
    }

    public static Constraint maxQueue(int maxMinutes, double priority) {
        return new Constraint("max_queue", ConstraintType.SOFT, Scope.PER_POI,
                priority, 0.15, "Max queue: " + maxMinutes + " min", (double) maxMinutes);
    }

    public static Constraint travelMode(String mode, double priority) {
        return new Constraint("travel_mode", ConstraintType.SOFT, Scope.ADJACENT_PAIR,
                priority, 0.1, "Travel mode: " + mode, mode);
    }
}
