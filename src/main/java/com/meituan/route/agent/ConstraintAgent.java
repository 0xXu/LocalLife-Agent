package com.meituan.route.agent;

import com.meituan.route.model.Constraint;
import com.meituan.route.model.Route;
import com.meituan.route.model.UserIntent;
import com.meituan.route.solver.ConstraintEngine;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.stream.Collectors;

/**
 * ConstraintAgent validates routes against constraints, handles conflict resolution,
 * and triggers re-planning when constraints cannot be satisfied.
 */
@Component
public class ConstraintAgent {

    private static final Logger log = LoggerFactory.getLogger(ConstraintAgent.class);

    private final ConstraintEngine constraintEngine;

    public ConstraintAgent(ConstraintEngine constraintEngine) {
        this.constraintEngine = constraintEngine;
    }

    /**
     * Analyze a set of routes against constraints and report results.
     */
    public ConstraintReport analyze(List<Route> routes, List<Constraint> constraints, UserIntent intent) {
        log.info("ConstraintAgent analyzing {} routes against {} constraints",
                routes.size(), constraints.size());

        var routeReports = routes.parallelStream()
                .map(route -> {
                    var result = constraintEngine.validate(route, constraints, intent);
                    double score = constraintEngine.scoreRoute(route, constraints);
                    return new RouteConstraintReport(route, result, score);
                })
                .toList();

        boolean allFeasible = routeReports.stream()
                .noneMatch(r -> r.result().hasHardViolations());

        // Best route by constraint satisfaction score
        var bestRoute = routeReports.stream()
                .max(Comparator.comparingDouble(RouteConstraintReport::score))
                .map(RouteConstraintReport::route)
                .orElse(null);

        return new ConstraintReport(routeReports, allFeasible, bestRoute, constraints);
    }

    /**
     * Parse adjustment query and extract new constraints.
     * e.g., "换家不排队的火锅" -> category=火锅, maxQueue=10
     */
    public List<Constraint> parseAdjustmentConstraints(String adjustment) {
        var constraints = new ArrayList<Constraint>();

        if (adjustment == null || adjustment.isBlank()) return constraints;

        // Check for cuisine replacements
        if (adjustment.contains("火锅")) {
            constraints.add(Constraint.category("RESTAURANT", 8));
        }
        if (adjustment.contains("日料") || adjustment.contains("日本料理")) {
            constraints.add(Constraint.category("RESTAURANT", 8));
        }

        // Queue tolerance
        if (adjustment.contains("不排队") || adjustment.contains("少排队")) {
            constraints.add(Constraint.maxQueue(10, 9));
        }

        // Rating requirement
        if (adjustment.matches(".*评分[以至少高于大于等于]*[\\d.]+.*")) {
            var matcher = java.util.regex.Pattern.compile("([\\d.]+)").matcher(adjustment);
            if (matcher.find()) {
                double rating = Double.parseDouble(matcher.group(1));
                constraints.add(Constraint.minRating(rating, 9));
            }
        }

        // Budget adjustment
        if (adjustment.contains("预算")) {
            var matcher = java.util.regex.Pattern.compile("(\\d+)").matcher(adjustment);
            if (matcher.find()) {
                double budget = Double.parseDouble(matcher.group(1));
                constraints.add(Constraint.budget(budget, 7));
            }
        }

        // Travel mode
        if (adjustment.contains("开车") || adjustment.contains("打车") || adjustment.contains("驾车")) {
            constraints.add(Constraint.travelMode("DRIVING", 6));
        } else if (adjustment.contains("少走路") || adjustment.contains("少步行") || adjustment.contains("少走")) {
            // "少走路" = WALKING but minimize walking distance
            constraints.add(Constraint.travelMode("WALKING", 8));
        } else if (adjustment.contains("走路") || adjustment.contains("步行")) {
            constraints.add(Constraint.travelMode("WALKING", 6));
        }

        return constraints;
    }

    /**
     * Generate a human-readable conflict report.
     */
    public String generateConflictReport(ConstraintReport report) {
        if (report.allFeasible()) return "所有方案均满足约束条件";

        var sb = new StringBuilder();
        sb.append("### 约束冲突报告\n\n");

        for (var routeReport : report.routeReports()) {
            if (!routeReport.result().hasHardViolations()) continue;

            sb.append("**").append(routeReport.route().name()).append("**\n");
            for (var violation : routeReport.result().violations()) {
                sb.append("- ").append(violation.message()).append("\n");
            }
            sb.append("\n");
        }

        sb.append("建议放松约束条件或选择其他路线方案。");
        return sb.toString();
    }

    public record RouteConstraintReport(Route route, ConstraintEngine.ConstraintResult result, double score) {}

    public record ConstraintReport(
            List<RouteConstraintReport> routeReports,
            boolean allFeasible,
            Route bestRoute,
            List<Constraint> constraints
    ) {}
}
