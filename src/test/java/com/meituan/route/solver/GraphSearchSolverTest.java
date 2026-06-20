package com.meituan.route.solver;

import com.meituan.route.model.Constraint;
import com.meituan.route.model.POI;
import com.meituan.route.model.UserIntent;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.LocalTime;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for GraphSearchSolver.
 */
class GraphSearchSolverTest {

    private GraphSearchSolver solver;
    private List<POI> testPOIs;
    private UserIntent intent;

    @BeforeEach
    void setUp() {
        solver = new GraphSearchSolver(new PreferenceScorer(), null);

        testPOIs = List.of(
                new POI("P1", "三里屯太古里", "SHOPPING", "购物中心",
                        39.933, 116.455, "三里屯路19号", "三里屯", "北京",
                        4.3, 200, 0, LocalTime.of(10, 0), LocalTime.of(22, 0), 120,
                        List.of("购物", "美食"), "", "时尚地标", 90),
                new POI("P2", "大董烤鸭店", "RESTAURANT", "北京菜",
                        39.9335, 116.453, "三里屯路11号", "三里屯", "北京",
                        4.6, 350, 30, LocalTime.of(11, 0), LocalTime.of(21, 30), 90,
                        List.of("烤鸭", "北京菜"), "", "著名烤鸭店", 92),
                new POI("P3", "火烧云傣家菜", "RESTAURANT", "云南菜",
                        39.9342, 116.452, "三里屯路19号3层", "三里屯", "北京",
                        4.6, 120, 35, LocalTime.of(11, 0), LocalTime.of(21, 30), 75,
                        List.of("云南菜", "网红"), "", "人气网红云南菜", 86),
                new POI("P4", "CGV影城", "ENTERTAINMENT", "电影院",
                        39.9338, 116.4545, "三里屯路19号6层", "三里屯", "北京",
                        4.3, 80, 10, LocalTime.of(9, 0), LocalTime.of(23, 59), 120,
                        List.of("电影", "娱乐"), "", "高品质影城", 80),
                new POI("P5", "Pageone书店", "CULTURE", "书店",
                        39.896, 116.395, "前门北京坊", "前门", "北京",
                        4.5, 60, 0, LocalTime.of(10, 0), LocalTime.of(22, 0), 60,
                        List.of("书店", "文艺"), "", "最美书店", 82)
        );

        intent = new UserIntent(
                "测试", "北京", "三里屯",
                List.of("RESTAURANT", "ENTERTAINMENT", "SHOPPING"), null,
                LocalTime.of(10, 0), LocalTime.of(22, 0),
                500, 2, 3.5, 30, "WALKING",
                "BEST_EXPERIENCE", null, List.of(), null
        );
    }

    @Test
    void testHaversine() {
        double distance = GraphSearchSolver.haversine(39.9, 116.4, 39.92, 116.41);
        assertTrue(distance > 0); // Should be ~2.2 km
        assertTrue(distance < 10); // Shouldn't be too large for nearby points
    }

    @Test
    void testEstimateTravelTime() {
        double time = solver.estimateTravelTime(testPOIs.get(0), testPOIs.get(1), "WALKING");
        assertTrue(time > 0);
        assertTrue(time < 60); // Walking between nearby POIs should be under 1 hour

        // Driving should be faster than walking
        double drivingTime = solver.estimateTravelTime(testPOIs.get(0), testPOIs.get(1), "DRIVING");
        assertTrue(drivingTime <= time);
    }

    @Test
    void testGeneratePlansWithSufficientPOIs() {
        var constraints = List.<Constraint>of(
                Constraint.timeWindow("10:00", "22:00", 10),
                Constraint.budget(500, 6)
        );

        var routes = solver.generatePlans(testPOIs, constraints, intent, 3);
        assertFalse(routes.isEmpty(), "Should generate at least one route");
        assertTrue(routes.size() <= 3, "Should generate at most 3 routes");
    }

    @Test
    void testGeneratePlansWithFewPOIs() {
        var fewPOIs = testPOIs.subList(0, 1);
        var constraints = List.<Constraint>of(
                Constraint.timeWindow("10:00", "22:00", 10)
        );

        var routes = solver.generatePlans(fewPOIs, constraints, intent, 3);
        assertFalse(routes.isEmpty(), "Should handle insufficient POIs gracefully");
    }

    @Test
    void testGeneratePlansDifferentObjectives() {
        var constraints = List.<Constraint>of(
                Constraint.timeWindow("10:00", "22:00", 10)
        );

        // BEST_EXPERIENCE
        var experienceIntent = new UserIntent("test", "北京", "三里屯",
                List.of("RESTAURANT", "SHOPPING"), null,
                LocalTime.of(10, 0), LocalTime.of(22, 0),
                0, 2, 3.5, 30, "WALKING",
                "BEST_EXPERIENCE", null, List.of(), null);
        var experienceRoutes = solver.generatePlans(testPOIs, constraints, experienceIntent, 1);
        assertFalse(experienceRoutes.isEmpty());

        // CHEAPEST
        var cheapIntent = new UserIntent("test", "北京", "三里屯",
                List.of("RESTAURANT", "SHOPPING"), null,
                LocalTime.of(10, 0), LocalTime.of(22, 0),
                0, 2, 3.5, 30, "WALKING",
                "CHEAPEST", null, List.of(), null);
        var cheapRoutes = solver.generatePlans(testPOIs, constraints, cheapIntent, 1);
        assertFalse(cheapRoutes.isEmpty());
    }

    @Test
    void testRouteHasSegments() {
        var constraints = List.<Constraint>of(
                Constraint.timeWindow("10:00", "22:00", 10)
        );

        var routes = solver.generatePlans(testPOIs, constraints, intent, 1);
        assertFalse(routes.isEmpty());

        var route = routes.get(0);
        assertFalse(route.segments().isEmpty(), "Route should have segments");
        assertTrue(route.totalCost() > 0);
        assertTrue(route.totalRating() > 0);
    }

    @Test
    void testEmptyCandidates() {
        var constraints = List.<Constraint>of();
        var routes = solver.generatePlans(List.of(), constraints, intent, 3);
        assertTrue(routes.isEmpty());
    }
}
