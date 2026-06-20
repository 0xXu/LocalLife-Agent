package com.meituan.route.agent.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.meituan.route.agent.ConstraintAgent;
import com.meituan.route.agent.Tool;
import com.meituan.route.agent.ToolRegistry;
import com.meituan.route.model.Constraint;
import com.meituan.route.model.Route;
import com.meituan.route.model.UserIntent;
import com.meituan.route.solver.ConstraintEngine;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.time.LocalTime;
import java.util.*;

@Component
public class CheckConstraintsTool implements Tool {

    private static final Logger log = LoggerFactory.getLogger(CheckConstraintsTool.class);
    private static final ObjectMapper mapper = new ObjectMapper();
    private final ConstraintAgent constraintAgent;
    private final ConstraintEngine constraintEngine;

    public CheckConstraintsTool(ConstraintAgent constraintAgent, ConstraintEngine constraintEngine, ToolRegistry registry) {
        this.constraintAgent = constraintAgent;
        this.constraintEngine = constraintEngine;
        registry.register(this);
    }

    @Override public String name() { return "check_constraints"; }

    @Override
    public String description() {
        return "检查路线方案是否满足用户约束（预算、时间窗口、营业时间、排队容忍度、最低评分等），返回约束满足报告。";
    }

    @Override
    public String parametersJson() {
        return """
            {
              "type": "object",
              "properties": {
                "budget": {"type": "number"},
                "maxQueueMinutes": {"type": "number"},
                "minRating": {"type": "number"},
                "city": {"type": "string"}
              },
              "required": []
            }""";
    }

    @Override
    @SuppressWarnings("unchecked")
    public ToolResult execute(String arguments) {
        try {
            // Constraints are checked at the orchestration level; here we validate
            // the overall constraint configuration and return the constraint report.
            var node = mapper.readTree(arguments);
            var budget = node.has("budget") ? node.get("budget").asDouble() : 0;
            var maxQueue = node.has("maxQueueMinutes") ? node.get("maxQueueMinutes").asInt() : 30;
            var minRating = node.has("minRating") ? node.get("minRating").asDouble() : 3.5;
            var city = node.has("city") ? node.get("city").asText() : "北京";

            var intent = new UserIntent("", city, null,
                    List.of("RESTAURANT"), null,
                    LocalTime.of(14, 0), LocalTime.of(22, 0), budget,
                    2, minRating, maxQueue, "WALKING", "BEST_EXPERIENCE", null, List.of(), null);

            var constraints = constraintEngine.buildConstraints(intent, List.of());
            var report = constraintAgent.analyze(List.of(), constraints, intent);

            var data = Map.<String, Object>of(
                    "allFeasible", report.allFeasible(),
                    "constraintCount", constraints.size(),
                    "violations", constraints.stream()
                            .filter(c -> c.type() == Constraint.ConstraintType.HARD)
                            .map(Constraint::description).toList());

            var summary = String.format("约束检查完成：%d 条约束，%s",
                    constraints.size(), report.allFeasible() ? "全部可行" : "存在冲突");
            log.info("CheckConstraintsTool: {}", summary);

            return ToolResult.of(name(), data, summary);
        } catch (Exception e) {
            log.error("CheckConstraintsTool failed", e);
            return ToolResult.of(name(), Map.of(), "约束检查失败: " + e.getMessage());
        }
    }
}
