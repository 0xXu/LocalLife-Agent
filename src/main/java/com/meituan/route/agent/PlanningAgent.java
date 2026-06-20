package com.meituan.route.agent;

import com.meituan.route.model.Route;
import com.meituan.route.model.Constraint;
import com.meituan.route.model.UserIntent;
import com.meituan.route.model.UserPreference;
import com.meituan.route.solver.ConstraintEngine;
import com.meituan.route.solver.GraphSearchSolver;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.stream.Collectors;

/**
 * PlanningAgent receives candidate POIs, builds a POI connectivity graph,
 * and generates 2-3 differentiated route plans.
 */
@Component
public class PlanningAgent {

    private static final Logger log = LoggerFactory.getLogger(PlanningAgent.class);

    private final GraphSearchSolver graphSolver;
    private final ConstraintEngine constraintEngine;

    public PlanningAgent(GraphSearchSolver graphSolver, ConstraintEngine constraintEngine) {
        this.graphSolver = graphSolver;
        this.constraintEngine = constraintEngine;
    }

    /**
     * Generate route plans from discovered POIs and user intent.
     */
    public PlanningResult plan(DiscoveryAgent.DiscoveryResult discovery, UserIntent intent,
                               List<Constraint> additionalConstraints) {
        return plan(discovery, intent, additionalConstraints, null);
    }

    /**
     * Generate route plans with optional user preference for personalization.
     */
    public PlanningResult plan(DiscoveryAgent.DiscoveryResult discovery, UserIntent intent,
                               List<Constraint> additionalConstraints, UserPreference preference) {
        log.info("PlanningAgent generating plans from {} candidates with goal: {}",
                discovery.candidates().size(), intent.optimizationGoal());

        var candidates = discovery.candidates();
        if (candidates.isEmpty()) {
            log.warn("No candidates available for planning");
            return new PlanningResult(List.of(), "没有找到符合条件的POI，请调整搜索条件", intent);
        }

        // Build constraints from intent
        var constraints = new ArrayList<>(constraintEngine.buildConstraints(intent, candidates));
        if (additionalConstraints != null) {
            constraints.addAll(additionalConstraints);
        }

        // Generate plans (3 by default) — pass preference for PREFERENCE goal
        var routes = graphSolver.generatePlans(candidates, constraints, intent, 3, preference);

        if (routes.isEmpty()) {
            // Try all relaxation levels in parallel — first success wins
            log.info("No initial solution, attempting constraint relaxation...");
            // For CHEAPEST goal, preserve budget — don't remove it entirely (Level 2)
            boolean preserveBudget = "CHEAPEST".equals(intent.optimizationGoal());
            var relaxations = constraintEngine.relaxConstraints(constraints, preserveBudget);
            routes = relaxations.parallelStream()
                    .map(relaxed -> graphSolver.generatePlans(candidates, relaxed, intent, 2))
                    .filter(r -> !r.isEmpty())
                    .findFirst()
                    .orElse(List.of());
            if (!routes.isEmpty()) {
                log.info("Found solution with relaxed constraints");
            }
        }

        if (routes.isEmpty()) {
            return new PlanningResult(List.of(), "约束条件过于严格，无法生成路线方案", intent);
        }

        // Validate routes against constraints and add budget-awareness
        var validatedRoutes = routes.stream()
                .map(route -> {
                    var result = constraintEngine.validate(route, constraints, intent);
                    if (result.hasHardViolations()) {
                        log.warn("Route {} has hard constraint violations", route.id());
                    }
                    return route;
                })
                .toList();

        // Budget ceiling detection: if all routes exceed user budget, add warning
        var warning = (String) null;
        if (intent.budget() > 0) {
            var allOverBudget = validatedRoutes.stream()
                    .allMatch(r -> r.totalCost() > intent.budget());
            if (allOverBudget) {
                var minCost = validatedRoutes.stream()
                        .mapToDouble(Route::totalCost)
                        .min().orElse(intent.budget());
                var overPercent = Math.round((minCost / intent.budget() - 1) * 100);
                warning = overPercent <= 20
                    ? "当前方案已接近预算天花板，人均¥" + Math.round(minCost) + "已是该需求下最优方案"
                    : "该区域/品类价格较高，人均¥" + Math.round(minCost) + "已达预算天花板，建议放宽预算或更换商圈";
                // Append warning to each route's description
                validatedRoutes = validatedRoutes.stream()
                        .map(r -> new Route(r.id(), r.name(), r.description(),
                                r.segments(), r.totalCost(), r.totalTravelTime(), r.totalRating(),
                                r.optimizationGoal(), r.satisfiedConstraints(), r.violatedSoftConstraints(),
                                r.score()))
                        .toList();
            }
        }

        log.info("PlanningAgent generated {} valid routes", validatedRoutes.size());
        return new PlanningResult(validatedRoutes, warning, intent);
    }

    /**
     * Re-plan with partial preservation (for adjustments).
     */
    public PlanningResult replan(DiscoveryAgent.DiscoveryResult discovery,
                                 UserIntent newIntent, List<Route.RouteSegment> keptPrefix,
                                 List<Constraint> additionalConstraints) {
        return replan(discovery, newIntent, keptPrefix, additionalConstraints, null);
    }

    /**
     * Re-plan with optional user preference.
     */
    public PlanningResult replan(DiscoveryAgent.DiscoveryResult discovery,
                                 UserIntent newIntent, List<Route.RouteSegment> keptPrefix,
                                 List<Constraint> additionalConstraints, UserPreference preference) {
        log.info("PlanningAgent re-planning with {} kept prefix POIs", keptPrefix.size());

        // Remove kept POIs from candidates to avoid duplicates
        var keptIds = keptPrefix.stream().map(s -> s.poi().id()).collect(Collectors.toSet());
        var remainingCandidates = discovery.candidates().stream()
                .filter(p -> !keptIds.contains(p.id()))
                .toList();

        // Create modified discovery with remaining candidates
        var modifiedDiscovery = new DiscoveryAgent.DiscoveryResult(
                remainingCandidates, discovery.categorizedPOIs(), newIntent);

        var result = plan(modifiedDiscovery, newIntent, additionalConstraints, preference);

        // Prepend kept prefix to each route
        if (!keptPrefix.isEmpty()) {
            var mergedRoutes = result.routes().stream()
                    .map(route -> {
                        var merged = new ArrayList<>(keptPrefix);
                        merged.addAll(route.segments());
                        double cost = merged.stream().mapToDouble(s -> s.poi().avgCost()).sum();
                        double rating = merged.stream().mapToDouble(s -> s.poi().rating()).sum();
                        double travelTime = merged.stream().mapToDouble(Route.RouteSegment::travelTimeFromPrevious).sum();
                        return new Route(route.id(), route.name(), route.description(),
                                merged, cost, travelTime, rating,
                                route.optimizationGoal(), route.satisfiedConstraints(),
                                route.violatedSoftConstraints(), route.score());
                    })
                    .toList();
            return new PlanningResult(mergedRoutes, result.warning(), newIntent);
        }

        return result;
    }

    public record PlanningResult(
            List<Route> routes,
            String warning,
            UserIntent intent
    ) {
        public boolean hasRoutes() {
            return routes != null && !routes.isEmpty();
        }
    }
}
