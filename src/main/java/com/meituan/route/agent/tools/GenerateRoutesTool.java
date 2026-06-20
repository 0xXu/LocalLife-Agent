package com.meituan.route.agent.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.meituan.route.agent.DiscoveryAgent;
import com.meituan.route.agent.PlanningAgent;
import com.meituan.route.agent.Tool;
import com.meituan.route.agent.ToolRegistry;
import com.meituan.route.data.DataService;
import com.meituan.route.model.POI;
import com.meituan.route.model.UserIntent;
import com.meituan.route.model.UserPreference;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.time.LocalTime;
import java.util.*;

@Component
public class GenerateRoutesTool implements Tool {

    private static final Logger log = LoggerFactory.getLogger(GenerateRoutesTool.class);
    private static final ObjectMapper mapper = new ObjectMapper();
    private final PlanningAgent planningAgent;
    private final DataService dataService;

    public GenerateRoutesTool(PlanningAgent planningAgent, DataService dataService, ToolRegistry registry) {
        this.planningAgent = planningAgent;
        this.dataService = dataService;
        registry.register(this);
    }

    @Override public String name() { return "generate_routes"; }

    @Override
    public String description() {
        return "根据候选POI和用户意图生成2-3条差异化路线方案（综合最优/效率优先/偏好优先）。";
    }

    @Override
    public String parametersJson() {
        return """
            {
              "type": "object",
              "properties": {
                "poiIds": {"type": "array", "items": {"type": "string"}, "description": "候选POI ID列表"},
                "city": {"type": "string"},
                "optimizationGoal": {"type": "string", "description": "BEST_EXPERIENCE / FASTEST / CHEAPEST"},
                "budget": {"type": "number"}
              },
              "required": ["poiIds", "city"]
            }""";
    }

    @Override
    public ToolResult execute(String arguments) {
        try {
            var node = mapper.readTree(arguments);
            var poiIds = new ArrayList<String>();
            if (node.has("poiIds")) for (var id : node.get("poiIds")) poiIds.add(id.asText());
            var city = node.has("city") ? node.get("city").asText() : "北京";
            var goal = node.has("optimizationGoal") ? node.get("optimizationGoal").asText() : "BEST_EXPERIENCE";
            var budget = node.has("budget") ? node.get("budget").asDouble() : 0;

            // Resolve POI IDs to POI objects
            var pois = new ArrayList<POI>();
            for (var id : poiIds) {
                var poi = dataService.findById(id).block();
                if (poi != null) pois.add(poi);
            }
            if (pois.isEmpty()) {
                // Fallback: load all from city
                pois.addAll(dataService.getAllByCity(city).collectList().block());
            }

            var intent = new UserIntent("", city, null,
                    List.of("RESTAURANT", "ATTRACTION", "SHOPPING", "ENTERTAINMENT", "CULTURE"),
                    null, LocalTime.of(14, 0), LocalTime.of(22, 0), budget,
                    2, 3.5, 30, "WALKING", goal, null, List.of(), null);

            var discovery = new DiscoveryAgent.DiscoveryResult(pois, Map.of(), intent);
            var planResult = planningAgent.plan(discovery, intent, List.of(), UserPreference.neutral());

            var routes = planResult.routes();
            var routeList = new ArrayList<Map<String, Object>>();
            for (var r : routes) {
                var poiNames = r.segments().stream().map(s -> s.poi().name()).toList();
                routeList.add(Map.<String, Object>of(
                        "id", r.id(), "name", r.name(),
                        "totalCost", r.totalCost(), "totalTravelTime", r.totalTravelTime(),
                        "optimizationGoal", r.optimizationGoal(),
                        "pois", poiNames, "score", r.score()));
            }

            var summary = String.format("生成了 %d 条路线方案", routes.size());
            log.info("GenerateRoutesTool: {}", summary);

            return ToolResult.of(name(), Map.of("routes", routeList, "count", routes.size(), "warning",
                    planResult.warning() != null ? planResult.warning() : ""), summary);
        } catch (Exception e) {
            log.error("GenerateRoutesTool failed", e);
            return ToolResult.of(name(), Map.of(), "路线生成失败: " + e.getMessage());
        }
    }
}
