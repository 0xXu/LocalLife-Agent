package com.meituan.route.agent;

import com.meituan.route.llm.RecommendationExplainer;
import com.meituan.route.model.Route;
import com.meituan.route.model.UserIntent;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * ExplanationAgent generates natural language explanations and recommendations
 * for each route plan, highlighting differences between options.
 */
@Component
public class ExplanationAgent {

    private final RecommendationExplainer explainer;

    public ExplanationAgent(RecommendationExplainer explainer) {
        this.explainer = explainer;
    }

    /**
     * Generate explanations for a set of route plans.
     */
    public ExplanationResult explain(List<Route> routes, UserIntent intent) {
        if (routes.isEmpty()) {
            return new ExplanationResult("暂无可用方案", "没有找到满足条件的路线方案", routes, null);
        }

        var detailed = explainer.compareRoutes(routes);
        var summary = buildSummary(routes, intent);

        return new ExplanationResult(summary, detailed, routes, detailed);
    }

    /**
     * Generate explanation for a single route (e.g., after adjustment).
     */
    public ExplanationResult explainSingle(Route route, UserIntent intent) {
        var text = explainer.explainRoute(route);
        var summary = buildSingleSummary(route);
        return new ExplanationResult(summary, text, List.of(route), text);
    }

    private String buildSummary(List<Route> routes, UserIntent intent) {
        var sb = new StringBuilder();

        String district = intent.district() != null ? intent.district() : intent.city();
        sb.append("为您规划了").append(routes.size()).append("条").append(district).append("路线方案：\n");

        for (int i = 0; i < routes.size(); i++) {
            var route = routes.get(i);
            String goalLabel = switch (route.optimizationGoal()) {
                case "BEST_EXPERIENCE" -> "体验最优";
                case "FASTEST" -> "最高效";
                case "CHEAPEST" -> "最省钱";
                default -> "方案" + (i + 1);
            };
            sb.append(i + 1).append(". ").append(goalLabel).append("：");
            sb.append(route.segments().size()).append("站 | ");
            sb.append("¥").append(String.format("%.0f", route.totalCost())).append(" | ");
            sb.append("均分").append(String.format("%.1f",
                    route.totalRating() / route.segments().size())).append("\n");
        }

        return sb.toString();
    }

    private String buildSingleSummary(Route route) {
        var names = route.segments().stream().map(s -> s.poi().name()).toList();
        return "为您更新路线：" + String.join(" → ", names);
    }

    public record ExplanationResult(
            String summary,
            String detailedExplanation,
            List<Route> routes,
            String comparisonHtml
    ) {}
}
