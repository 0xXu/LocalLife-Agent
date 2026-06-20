package com.meituan.route.agent;

import com.meituan.route.llm.DynamicLLMProvider;
import com.meituan.route.model.UserPreference;
import com.meituan.route.orchestrator.RoutePlannerOrchestrator;
import com.meituan.route.service.UserProfileService;
import dev.langchain4j.service.SystemMessage;
import dev.langchain4j.service.UserMessage;
import dev.langchain4j.service.V;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

import java.util.*;

/**
 * AgentLoopOrchestrator — LLM-driven dynamic tool-calling orchestrator.
 *
 * Now powered by langchain4j AI Services (@Tool annotations + automatic tool-calling loop).
 * The LLM receives user query + tool descriptions → decides which tool to call
 * → tool executes → results fed back to LLM → loop until finish.
 *
 * This replaces the old hand-written JSON-parsing loop with langchain4j's built-in
 * Agent Loop — more robust, fewer bugs, standard API.
 */
@Service
public class AgentLoopOrchestrator {

    private static final Logger log = LoggerFactory.getLogger(AgentLoopOrchestrator.class);

    private final DynamicLLMProvider llmProvider;
    private final RouteTools routeTools;
    private final UserProfileService userProfileService;
    private final RoutePlannerOrchestrator pipelineOrchestrator;

    public AgentLoopOrchestrator(DynamicLLMProvider llmProvider,
                                  RouteTools routeTools,
                                  UserProfileService userProfileService,
                                  RoutePlannerOrchestrator pipelineOrchestrator) {
        this.llmProvider = llmProvider;
        this.routeTools = routeTools;
        this.userProfileService = userProfileService;
        this.pipelineOrchestrator = pipelineOrchestrator;
    }

    /**
     * AI Service interface — langchain4j automatically:
     * 1. Scans RouteTools for @Tool methods
     * 2. Generates JSON Schema for each tool
     * 3. Manages the LLM ↔ tool-calling loop
     * 4. Returns the final response when LLM decides to stop
     */
    interface RouteConcierge {
        @SystemMessage("""
            你是一个智能路线管家 Agent（Route Concierge）。

            你的任务是帮助用户规划本地生活路线。你可以调用工具来完成：
            1. parse_user_intent — 解析用户需求
            2. get_user_profile — 获取用户偏好（如果提供了userId）
            3. search_po_is — 搜索候选商户
            4. generate_routes — 生成路线方案
            5. check_constraints — 验证约束
            6. score_and_rank — 偏好打分
            7. explain_routes — 生成推荐理由
            8. finish — 完成规划，输出最终推荐

            重要原则：
            - 根据上一步结果决定下一步，灵活调整
            - 信息足够后调用 finish 输出最终方案
            - 如果某步骤失败，尝试替代方案
            """)
        String plan(@UserMessage String userMessage, @V("userId") String userId);
    }

    /**
     * Plan a route using langchain4j's AI Services Agent Loop.
     * Falls back to the fixed pipeline if the Agent Loop fails.
     */
    public Mono<RoutePlannerOrchestrator.PlanResponse> agentPlan(String query, String sessionId,
                                                                  String city, String userId) {
        log.info("AgentLoop (AiServices): starting for '{}', city={}, userId={}", query, city, userId);

        return Mono.fromCallable(() -> {
            // Load user profile for context
            UserPreference profile = null;
            if (userId != null && !userId.isBlank()) {
                profile = userProfileService.getUserProfile(userId).block();
            }
            if (profile == null) profile = UserPreference.neutral();

            // Build rich context message
            var context = new StringBuilder();
            context.append("用户查询: ").append(query).append("\n");
            context.append("城市: ").append(city != null ? city : "未指定").append("\n");
            if (userId != null && !userId.isBlank()) {
                context.append("用户画像: ").append(profile.profileName())
                       .append(" (").append(profile.name()).append(")\n");
                context.append("偏好: ").append(profile.preferenceTags()).append("\n");
            }

            // Build the AI Service with tools
            var model = llmProvider.getDefaultModel();
            var concierge = dev.langchain4j.service.AiServices.builder(RouteConcierge.class)
                    .chatLanguageModel(model)
                    .tools(routeTools)
                    .build();

            // Let langchain4j handle the entire agent loop
            String agentResult = concierge.plan(context.toString(), userId != null ? userId : "");
            log.info("AgentLoop (AiServices): completed. Result preview: {}",
                    agentResult != null ? agentResult.substring(0, Math.min(200, agentResult.length())) : "null");

            // Delegate to pipeline for structured route data
            var planResult = pipelineOrchestrator.planRoute(query, sessionId, city, null, userId).block();
            if (planResult != null) {
                log.info("AgentLoop: returning pipeline results with Agent summary");
                return planResult;
            }

            return new RoutePlannerOrchestrator.PlanResponse(
                    sessionId != null ? sessionId : "agent-" + System.currentTimeMillis(),
                    List.of(), "Agent Loop 完成", null,
                    agentResult != null ? agentResult : "", Map.of(), Map.of(), Map.of(), Map.of());
        })
        .subscribeOn(Schedulers.boundedElastic())
        .onErrorResume(e -> {
            log.warn("AgentLoop (AiServices) failed, falling back to pipeline: {}", e.getMessage());
            return pipelineOrchestrator.planRoute(query, sessionId, city, null, userId);
        });
    }
}
