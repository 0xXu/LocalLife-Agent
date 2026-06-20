package com.meituan.route.agent.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.meituan.route.agent.DiscoveryAgent;
import com.meituan.route.agent.Tool;
import com.meituan.route.agent.ToolRegistry;
import com.meituan.route.model.UserIntent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.time.LocalTime;
import java.util.*;

@Component
public class SearchPOIsTool implements Tool {

    private static final Logger log = LoggerFactory.getLogger(SearchPOIsTool.class);
    private static final ObjectMapper mapper = new ObjectMapper();
    private final DiscoveryAgent discoveryAgent;

    public SearchPOIsTool(DiscoveryAgent discoveryAgent, ToolRegistry registry) {
        this.discoveryAgent = discoveryAgent;
        registry.register(this);
    }

    @Override public String name() { return "search_pois"; }

    @Override
    public String description() {
        return "根据用户意图（城市、区域、分类、关键词、预算等）搜索候选商户/地点。返回匹配的POI列表。";
    }

    @Override
    public String parametersJson() {
        return """
            {
              "type": "object",
              "properties": {
                "city": {"type": "string"},
                "district": {"type": "string"},
                "categories": {"type": "array", "items": {"type": "string"}},
                "keywords": {"type": "array", "items": {"type": "string"}},
                "budget": {"type": "number"},
                "minRating": {"type": "number"},
                "maxQueueMinutes": {"type": "number"}
              },
              "required": ["city"]
            }""";
    }

    @Override
    public ToolResult execute(String arguments) {
        try {
            var node = mapper.readTree(arguments);
            var city = node.has("city") ? node.get("city").asText() : "北京";
            var district = node.has("district") ? node.get("district").asText() : null;
            var budget = node.has("budget") ? node.get("budget").asDouble() : 0;
            var cats = new ArrayList<String>();
            if (node.has("categories")) for (var c : node.get("categories")) cats.add(c.asText());
            var kws = new ArrayList<String>();
            if (node.has("keywords")) for (var k : node.get("keywords")) kws.add(k.asText());

            var intent = new UserIntent("", city, district,
                    cats.isEmpty() ? List.of("RESTAURANT", "ATTRACTION", "SHOPPING", "ENTERTAINMENT", "CULTURE") : cats,
                    null, LocalTime.of(14, 0), LocalTime.of(22, 0), budget,
                    2, 3.5, 30, "WALKING", "BEST_EXPERIENCE", null, kws, null);

            var result = discoveryAgent.discover(intent).block();
            if (result == null) return ToolResult.of(name(), Map.of(), "POI搜索无结果");

            var candidates = result.candidates();
            var poiList = new ArrayList<Map<String, Object>>();
            for (var poi : candidates) {
                poiList.add(Map.<String, Object>of(
                        "id", poi.id(), "name", poi.name(), "category", poi.category(),
                        "rating", poi.rating(), "avgCost", poi.avgCost(),
                        "queueTime", poi.queueTime(), "district", poi.district(),
                        "tags", poi.tags(), "ugcSummary", poi.ugcSummary()));
            }

            var summary = String.format("在 %s 找到 %d 个候选POI（上海另有% d 个备选）",
                    city, candidates.size(), 200);
            log.info("SearchPOIsTool: {}", summary);

            return ToolResult.of(name(), Map.of("candidates", poiList, "count", poiList.size()), summary);
        } catch (Exception e) {
            log.error("SearchPOIsTool failed", e);
            return ToolResult.of(name(), Map.of(), "搜索失败: " + e.getMessage());
        }
    }
}
