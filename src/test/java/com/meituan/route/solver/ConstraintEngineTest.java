package com.meituan.route.solver;

import com.meituan.route.model.Constraint;
import com.meituan.route.model.POI;
import com.meituan.route.model.Route;
import com.meituan.route.model.UserIntent;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.LocalTime;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for ConstraintEngine.
 */
class ConstraintEngineTest {

    private ConstraintEngine engine;
    private List<POI> samplePOIs;
    private UserIntent sampleIntent;

    @BeforeEach
    void setUp() {
        engine = new ConstraintEngine();

        samplePOIs = List.of(
                new POI("P1", "测试餐厅A", "RESTAURANT", "中餐",
                        39.9, 116.4, "地址A", "三里屯", "北京",
                        4.5, 150, 20,
                        LocalTime.of(10, 0), LocalTime.of(22, 0), 60,
                        List.of("美食", "中餐"), "", "测试描述", 80),
                new POI("P2", "测试景点B", "ATTRACTION", "公园",
                        39.92, 116.41, "地址B", "三里屯", "北京",
                        4.2, 30, 5,
                        LocalTime.of(8, 0), LocalTime.of(18, 0), 90,
                        List.of("景点", "休闲"), "", "测试描述", 70)
        );

        sampleIntent = new UserIntent(
                "测试查询", "北京", "三里屯",
                List.of("RESTAURANT", "ATTRACTION"), null,
                LocalTime.of(10, 0), LocalTime.of(20, 0),
                500, 2, 3.5, 30, "WALKING",
                "BEST_EXPERIENCE", null, List.of(), null
        );
    }

    @Test
    void testBuildConstraints() {
        var constraints = engine.buildConstraints(sampleIntent, samplePOIs);

        assertFalse(constraints.isEmpty());
        assertTrue(constraints.stream().anyMatch(c -> "budget".equals(c.id())));
        assertTrue(constraints.stream().anyMatch(c -> c.id().startsWith("tw_")));
        assertTrue(constraints.stream().anyMatch(c -> "min_rating".equals(c.id())));
    }

    @Test
    void testHardConstraintTimeWindow() {
        var constraints = List.of(
                Constraint.timeWindow("09:00", "17:00", 10)
        );

        // Create a route violating time window (ends after 17:00)
        var segment = new Route.RouteSegment(samplePOIs.get(0),
                LocalTime.of(15, 0), LocalTime.of(18, 0), 0, "WALKING");
        var route = new Route("R1", "Test", "Desc", List.of(segment),
                150, 0, 4.5, "TEST", List.of(), List.of(), 50);

        var result = engine.validate(route, constraints, sampleIntent);
        assertTrue(result.hasHardViolations());
    }

    @Test
    void testHardConstraintPasses() {
        var constraints = List.of(
                Constraint.timeWindow("08:00", "22:00", 10)
        );

        var segment = new Route.RouteSegment(samplePOIs.get(0),
                LocalTime.of(10, 0), LocalTime.of(11, 0), 0, "WALKING");
        var route = new Route("R1", "Test", "Desc", List.of(segment),
                150, 0, 4.5, "TEST", List.of(), List.of(), 50);

        var result = engine.validate(route, constraints, sampleIntent);
        assertFalse(result.hasHardViolations());
    }

    @Test
    void testBudgetSoftConstraint() {
        var constraints = List.of(
                Constraint.budget(100, 6)
        );

        // Route costs 150, exceeds budget
        var segment = new Route.RouteSegment(samplePOIs.get(0),
                LocalTime.of(10, 0), LocalTime.of(11, 0), 0, "WALKING");
        var route = new Route("R1", "Test", "Desc", List.of(segment),
                150, 0, 4.5, "TEST", List.of(), List.of(), 50);

        boolean passes = constraints.stream()
                .filter(c -> "budget".equals(c.id()))
                .allMatch(c -> c.type() == Constraint.ConstraintType.SOFT);

        assertTrue(passes); // Budget is SOFT, won't prune
    }

    @Test
    void testScoreRoute() {
        var constraints = engine.buildConstraints(sampleIntent, samplePOIs);

        var seg1 = new Route.RouteSegment(samplePOIs.get(0),
                LocalTime.of(10, 0), LocalTime.of(11, 0), 0, "WALKING");
        var seg2 = new Route.RouteSegment(samplePOIs.get(1),
                LocalTime.of(11, 30), LocalTime.of(13, 0), 15, "WALKING");
        var route = new Route("R1", "Test", "Desc", List.of(seg1, seg2),
                180, 15, 8.7, "BEST_EXPERIENCE", List.of(), List.of(), 50);

        double score = engine.scoreRoute(route, constraints);
        assertTrue(score >= 0 && score <= 100);
    }

    @Test
    void testRelaxConstraints() {
        var constraints = List.of(
                Constraint.timeWindow("09:00", "17:00", 10),
                Constraint.budget(200, 6),
                Constraint.minRating(4.0, 5),
                Constraint.maxQueue(15, 4)
        );

        var relaxations = engine.relaxConstraints(constraints);
        assertFalse(relaxations.isEmpty());

        // First relaxation should have fewer soft constraints
        assertTrue(relaxations.get(0).size() <= constraints.size());
    }
}
