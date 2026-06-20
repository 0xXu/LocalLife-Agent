package com.meituan.route;

import com.meituan.route.llm.IntentParser;
import com.meituan.route.model.IntentAnalysisResult;
import com.meituan.route.model.UserIntent;
import com.meituan.route.model.UserPreference;
import com.meituan.route.orchestrator.RoutePlannerOrchestrator;
import com.meituan.route.service.UserProfileService;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

import com.meituan.route.data.DataService;
import com.meituan.route.model.POI;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/route")
public class RouteController {

    private final RoutePlannerOrchestrator orchestrator;
    private final IntentParser intentParser;
    private final UserProfileService userProfileService;
    private final com.meituan.route.agent.AgentLoopOrchestrator agentLoopOrchestrator;
    private final DataService dataService;

    public RouteController(RoutePlannerOrchestrator orchestrator, IntentParser intentParser,
                           UserProfileService userProfileService,
                           com.meituan.route.agent.AgentLoopOrchestrator agentLoopOrchestrator,
                           DataService dataService) {
        this.orchestrator = orchestrator;
        this.intentParser = intentParser;
        this.userProfileService = userProfileService;
        this.agentLoopOrchestrator = agentLoopOrchestrator;
        this.dataService = dataService;
    }

    @PostMapping(value = "/plan", produces = MediaType.APPLICATION_JSON_VALUE)
    public Mono<RoutePlannerOrchestrator.PlanResponse> plan(@RequestBody PlanRequest request,
                                                             ServerHttpRequest httpRequest) {
        var userId = resolveUserId(request.userId(), httpRequest);
        return orchestrator.planRoute(request.query(), request.sessionId(), request.city(),
                request.intent(), userId);
    }

    @PostMapping(value = "/analyze", produces = MediaType.APPLICATION_JSON_VALUE)
    public Mono<IntentAnalysisResult> analyze(@RequestBody AnalyzeRequest request) {
        return Mono.fromCallable(() ->
                intentParser.analyzeWithCompleteness(request.query(), request.sessionId(), request.city()));
    }

    @PostMapping(value = "/smart-plan", produces = MediaType.APPLICATION_JSON_VALUE)
    public Mono<Map<String, Object>> smartPlan(@RequestBody AnalyzeRequest request,
                                                ServerHttpRequest httpRequest) {
        var userId = resolveUserId(request.userId(), httpRequest);
        return Mono.fromCallable(() ->
                intentParser.analyzeWithCompleteness(request.query(), request.sessionId(), request.city()))
                .subscribeOn(Schedulers.boundedElastic())
                .flatMap(analysis -> {
                    var stage = analysis.stage();
                    var result = new java.util.LinkedHashMap<String, Object>();
                    result.put("stage", stage);
                    result.put("summaryText", analysis.summaryText());

                    if ("followup".equals(stage) || "conflict".equals(stage)) {
                        result.put("intent", analysis.intent());
                        result.put("followupQuestions", analysis.followupQuestions());
                        result.put("conflicts", analysis.conflicts());
                        result.put("missingFields", analysis.missingFields());
                        result.put("routes", null);
                        return Mono.just(result);
                    }

                    result.put("intent", analysis.intent());
                    return orchestrator.planRoute(
                            request.query(),
                            analysis.intent().sessionId(),
                            request.city(),
                            analysis.intent(),
                            userId)
                            .map(plan -> {
                                result.put("routes", plan.routes());
                                result.put("warning", plan.warning());
                                result.put("recommendedRoute", plan.recommendedRoute());
                                result.put("explanation", plan.explanation());
                                result.put("sessionId", plan.sessionId());
                                result.put("preferenceMatchTags", plan.preferenceMatchTags());
                                result.put("preferenceScores", plan.preferenceScores());
                                result.put("ugcMatchTags", plan.ugcMatchTags());
                                result.put("ugcSummaries", plan.ugcSummaries());
                                return result;
                            });
                });
    }

    @PostMapping(value = "/adjust", produces = MediaType.APPLICATION_JSON_VALUE)
    public Mono<RoutePlannerOrchestrator.PlanResponse> adjust(@RequestBody AdjustRequest request,
                                                               ServerHttpRequest httpRequest) {
        var userId = resolveUserId(request.userId(), httpRequest);
        return orchestrator.adjustRoute(request.sessionId(), request.adjustment(), request.city(), userId);
    }

    @GetMapping(value = "/compare/{sessionId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public Mono<RoutePlannerOrchestrator.CompareResponse> compare(@PathVariable String sessionId) {
        return orchestrator.getComparison(sessionId);
    }

    /**
     * POST /api/route/agent-plan — LLM-driven Agent Loop planning.
     * Uses the new 1-Agent + Tools architecture: the LLM dynamically decides
     * which tools to call instead of following a fixed pipeline.
     * Falls back to the existing pipeline if the Agent Loop cannot complete.
     */
    @PostMapping(value = "/agent-plan", produces = MediaType.APPLICATION_JSON_VALUE)
    public Mono<RoutePlannerOrchestrator.PlanResponse> agentPlan(@RequestBody PlanRequest request,
                                                                  ServerHttpRequest httpRequest) {
        var userId = resolveUserId(request.userId(), httpRequest);
        return agentLoopOrchestrator.agentPlan(request.query(), request.sessionId(), request.city(), userId);
    }

    /**
     * GET /api/route/pois?city=北京 — Return POI data for a city.
     * Unifies frontend and backend POI data: frontend fetches from this endpoint
     * instead of maintaining a separate mock dataset.
     */
    @GetMapping(value = "/pois", produces = MediaType.APPLICATION_JSON_VALUE)
    public Mono<List<Map<String, Object>>> getPOIs(@RequestParam(defaultValue = "北京") String city) {
        return dataService.getAllByCity(city)
                .map(poi -> Map.<String, Object>ofEntries(
                        Map.entry("id", poi.id()),
                        Map.entry("name", poi.name()),
                        Map.entry("category", poi.category()),
                        Map.entry("subCategory", poi.subCategory()),
                        Map.entry("district", poi.district()),
                        Map.entry("city", poi.city()),
                        Map.entry("rating", poi.rating()),
                        Map.entry("avgCost", poi.avgCost()),
                        Map.entry("queueTime", poi.queueTime()),
                        Map.entry("tags", poi.tags()),
                        Map.entry("riskTags", poi.riskTags()),
                        Map.entry("ugcTags", poi.ugcTags()),
                        Map.entry("ugcSummary", poi.ugcSummary()),
                        Map.entry("imageUrl", poi.imageUrl()),
                        Map.entry("address", poi.address()),
                        Map.entry("description", poi.description()),
                        Map.entry("popularityScore", poi.popularityScore()),
                        Map.entry("lat", poi.lat()),
                        Map.entry("lng", poi.lng())
                ))
                .collectList();
    }

    @GetMapping(value = "/health", produces = MediaType.APPLICATION_JSON_VALUE)
    public Mono<Map<String, String>> health() {
        return Mono.just(Map.of("status", "UP", "service", "AI Route Planner"));
    }

    /**
     * GET /api/route/profiles — List all user profiles for the frontend user switcher.
     */
    @GetMapping(value = "/profiles", produces = MediaType.APPLICATION_JSON_VALUE)
    public Mono<List<UserPreference>> listProfiles() {
        return userProfileService.listAllProfiles();
    }

    /**
     * Resolve userId: prefer AuthFilter's exchange attribute (from JWT),
     * fall back to request body parameter for backward compatibility.
     */
    private String resolveUserId(String bodyUserId, ServerHttpRequest httpRequest) {
        // AuthFilter sets this attribute after JWT validation
        var authUserId = httpRequest.getAttributes().get("userId");
        if (authUserId instanceof String uid && !uid.isBlank()) {
            return uid;
        }
        // Fallback: use body userId (for backward compatibility)
        return bodyUserId;
    }

    // Request DTOs
    public record PlanRequest(String query, String sessionId, String city, UserIntent intent, String userId) {}
    public record AnalyzeRequest(String query, String sessionId, String city, String userId) {}
    public record AdjustRequest(String sessionId, String adjustment, String city, String userId) {}
}
