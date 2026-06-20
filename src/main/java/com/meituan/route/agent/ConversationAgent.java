package com.meituan.route.agent;

import com.meituan.route.llm.IntentParser;
import com.meituan.route.model.UserIntent;
import com.meituan.route.state.SessionStateManager;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

/**
 * ConversationAgent handles multi-turn dialogue, maintains session context,
 * and outputs a structured UserIntent.
 *
 * Responsibilities:
 * - Parse natural language queries into structured intents
 * - Maintain conversation history across turns
 * - Detect intent changes for incremental adjustments
 */
@Component
public class ConversationAgent {

    private static final Logger log = LoggerFactory.getLogger(ConversationAgent.class);

    private final IntentParser intentParser;
    private final SessionStateManager sessionManager;

    public ConversationAgent(IntentParser intentParser, SessionStateManager sessionManager) {
        this.intentParser = intentParser;
        this.sessionManager = sessionManager;
    }

    /**
     * Synchronous entry point kept for backward compatibility.
     */
    public ConversationResult process(String query, String sessionId) {
        return processAsync(query, sessionId, null).block();
    }

    /**
     * Reactive entry point (no city hint — defaults to "北京").
     */
    public Mono<ConversationResult> processAsync(String query, String sessionId) {
        return processAsync(query, sessionId, null);
    }

    public Mono<ConversationResult> processAsync(String query, String sessionId, String cityHint) {
        return processAsync(query, sessionId, cityHint, null, null);
    }

    public Mono<ConversationResult> processAsync(String query, String sessionId, String cityHint,
                                                   String userProvider, String userApiKey) {
        log.info("ConversationAgent processing query: '{}' for session: {}, cityHint={}, userApiKey={}",
                query, sessionId, cityHint, userApiKey != null);

        String actualSessionId = sessionId;
        if (actualSessionId == null || actualSessionId.isBlank()) {
            actualSessionId = sessionManager.createSession();
            log.info("Created new session: {}", actualSessionId);
        }

        final var sid = actualSessionId;

        // Step 1: Load session state first, then pass previousIntent to LLM
        // This ensures the LLM knows about prior requirements (city, budget, categories, etc.)
        var sessionMono = Mono.fromCallable(() -> sessionManager.getSession(sid))
                .subscribeOn(Schedulers.boundedElastic());

        // Step 2: Use session context to inform LLM parsing — preserves user's original
        // requirements across multiple conversation turns
        var intentWithContextMono = sessionMono.flatMap(existingSession -> {
            UserIntent previousIntent = null;
            if (existingSession.isPresent() && existingSession.get().currentIntent() != null) {
                previousIntent = existingSession.get().currentIntent();
                log.info("Loaded previous intent for session {}: city={}, district={}, categories={}, keywords={}, specialRequest={}",
                        sid, previousIntent.city(), previousIntent.district(),
                        previousIntent.preferredCategories(), previousIntent.keywords(),
                        previousIntent.specialRequest());
            }
            return intentParser.parseAsync(query, sid, cityHint, previousIntent, userProvider, userApiKey);
        });

        return Mono.zip(intentWithContextMono, sessionMono).map(tuple -> {
            var intent = tuple.getT1();
            var existingSession = tuple.getT2();

            boolean isAdjustment = existingSession.isPresent()
                    && existingSession.get().snapshots() != null
                    && !existingSession.get().snapshots().isEmpty();

            if (isAdjustment) {
                sessionManager.updateIntent(sid, intent);
            }

            String adjustmentQuery = null;
            if (isAdjustment && isAdjustmentQuery(query)) {
                adjustmentQuery = query;
            }

            log.info("ConversationAgent produced intent: city={}, district={}, categories={}",
                    intent.city(), intent.district(), intent.preferredCategories());

            return new ConversationResult(sid, intent, adjustmentQuery,
                    existingSession.map(s -> s.currentIntent()).orElse(null));
        });
    }

    private boolean isAdjustmentQuery(String query) {
        var adj = query.toLowerCase();
        return adj.contains("换") || adj.contains("改") || adj.contains("调整")
                || adj.contains("不要") || adj.contains("替换") || adj.contains("去掉")
                || adj.contains("少走") || adj.contains("便宜") || adj.contains("排队")
                || adj.contains("口味") || adj.contains("出片") || adj.contains("地铁")
                || adj.contains("安静") || adj.contains("省时");
    }

    /**
     * Result from ConversationAgent processing.
     */
    public record ConversationResult(
            String sessionId,
            UserIntent intent,
            String adjustmentQuery,
            UserIntent previousIntent
    ) {
        public boolean isAdjustment() {
            return adjustmentQuery != null;
        }
    }
}
