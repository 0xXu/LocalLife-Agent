package com.meituan.route.llm;

import com.meituan.route.model.POI;
import com.meituan.route.model.Route;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.stream.Collectors;

/**
 * Generates natural language explanations and recommendations for routes.
 */
@Component
public class RecommendationExplainer {

    private static final Map<String, List<String>> TAG_PRAISE = Map.ofEntries(
            Map.entry("拍照好看", List.of("ins风出片圣地", "随手一拍就是大片", "朋友圈素材+1")),
            Map.entry("约会", List.of("浪漫指数爆表", "约会必去", "氛围感满分")),
            Map.entry("亲子", List.of("遛娃好去处", "孩子玩到不想走")),
            Map.entry("网红", List.of("小红书爆款", "排队也值得", "顶流打卡地")),
            Map.entry("历史", List.of("穿越时空的对话", "感受历史厚重感")),
            Map.entry("文化", List.of("文化熏陶之旅", "涨知识的好地方")),
            Map.entry("美食", List.of("味蕾的极致享受", "吃货的天堂")),
            Map.entry("排队", List.of("人气爆棚", "口碑之选")),
            Map.entry("免费", List.of("性价比之王", "不花钱的快乐"))
    );

    /**
     * Generate a detailed explanation for a single route.
     */
    public String explainRoute(Route route) {
        var sb = new StringBuilder();
        sb.append("## ").append(route.name()).append("\n\n");
        sb.append(route.description()).append("\n\n");
        sb.append("### 行程详情\n\n");

        for (int i = 0; i < route.segments().size(); i++) {
            var seg = route.segments().get(i);
            var poi = seg.poi();

            sb.append("**").append(i + 1).append(". ")
                    .append(poi.name()).append("**\n");
            sb.append("- 到达时间：").append(seg.arrivalTime()).append("\n");
            sb.append("- 离开时间：").append(seg.departureTime()).append("\n");
            sb.append("- 推荐理由：").append(generateReason(poi)).append("\n");
            sb.append("- 预计花费：¥").append(String.format("%.0f", poi.avgCost())).append("\n");
            sb.append("- 用户评分：").append(poi.rating()).append("\n");

            if (i < route.segments().size() - 1) {
                sb.append("- 前往下一站：步行约")
                        .append(String.format("%.0f", seg.travelTimeFromPrevious()))
                        .append("分钟\n");
            }
            sb.append("\n");
        }

        sb.append("### 费用汇总\n\n");
        sb.append("- 总花费：¥").append(String.format("%.0f", route.totalCost())).append("\n");
        sb.append("- 总步行时间：约").append(String.format("%.0f", route.totalTravelTime())).append("分钟\n");
        sb.append("- 综合评分：").append(String.format("%.1f",
                route.totalRating() / route.segments().size())).append("/5.0\n");

        return sb.toString();
    }

    /**
     * Generate a comparison of multiple routes.
     */
    public String compareRoutes(List<Route> routes) {
        if (routes.isEmpty()) return "暂无可用方案";
        if (routes.size() == 1) return explainRoute(routes.get(0));

        var sb = new StringBuilder();
        sb.append("# 路线方案对比\n\n");
        sb.append("为您生成了 **").append(routes.size()).append("** 个方案：\n\n");

        for (int i = 0; i < routes.size(); i++) {
            var route = routes.get(i);
            sb.append("### 🚀 方案").append(i + 1).append("：").append(route.name()).append("\n\n");

            var poiNames = route.segments().stream()
                    .map(s -> s.poi().name())
                    .collect(Collectors.joining(" → "));
            sb.append("路线：").append(poiNames).append("\n\n");

            sb.append("- 💰 费用：¥").append(String.format("%.0f", route.totalCost())).append("\n");
            sb.append("- ⭐ 均分：").append(String.format("%.1f",
                    route.totalRating() / route.segments().size())).append("\n");
            sb.append("- 🚶 路程：约").append(String.format("%.0f", route.totalTravelTime())).append("分钟\n\n");

            // Main reason
            sb.append("**推荐理由：** ").append(generateRouteReason(route)).append("\n\n");
            sb.append("---\n\n");
        }

        // Final recommendation
        var best = routes.get(0);
        sb.append("### 💡 小编推荐\n\n");
        sb.append("推荐 **").append(best.name()).append("**：");
        sb.append(generateRouteReason(best)).append("\n");

        return sb.toString();
    }

    private String generateReason(POI poi) {
        var reasons = new ArrayList<String>();

        if (poi.rating() >= 4.5) {
            reasons.add("评分高达" + poi.rating() + "分");
        }

        // UGC reviews take precedence — real user feedback is more trustworthy
        if (poi.hasUGC() && !poi.ugcSummary().isBlank()) {
            reasons.add("真实评价：" + poi.ugcSummary());
        } else {
            for (var tag : poi.tags()) {
                var praises = TAG_PRAISE.get(tag);
                if (praises != null && !praises.isEmpty()) {
                    reasons.add(praises.get(new Random().nextInt(praises.size())));
                }
            }
        }

        if (reasons.isEmpty()) {
            reasons.add(poi.description());
        }

        return String.join("，", reasons);
    }

    /**
     * Generate explanation that highlights UGC influence on route ranking.
     * When UGC data contradicted raw ratings, make that visible.
     */
    public String generateUGCExplanation(Route route) {
        var sb = new StringBuilder();
        var ugcPOIs = route.segments().stream()
                .filter(s -> s.poi().hasUGC())
                .toList();

        if (ugcPOIs.isEmpty()) return "";

        sb.append("💬 来自用户评价：");
        var parts = new ArrayList<String>();
        for (var seg : ugcPOIs) {
            var poi = seg.poi();
            if (!poi.ugcSummary().isBlank()) {
                parts.add(poi.name() + " — " + poi.ugcSummary());
            }
        }
        sb.append(String.join("；", parts));
        return sb.toString();
    }

    private String generateRouteReason(Route route) {
        // Check if UGC influenced this route
        var hasUGC = route.segments().stream().anyMatch(s -> s.poi().hasUGC());
        var ugcSuffix = hasUGC ? "，结合真实用户评价优化" : "";

        return switch (route.optimizationGoal()) {
            case "BEST_EXPERIENCE" -> "精选高评分POI，体验最佳，适合享受型的您" + ugcSuffix;
            case "FASTEST" -> "路线最紧凑高效，省时省力，适合时间紧张的你" + ugcSuffix;
            case "CHEAPEST" -> "严格控制预算，性价比之选，花少钱玩尽兴" + ugcSuffix;
            default -> route.segments().size() + "个地点串联，合理规划时间" + ugcSuffix;
        };
    }
}
