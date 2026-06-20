package com.meituan.route.orchestrator;

import com.meituan.route.agent.*;
import com.meituan.route.model.Route;
import com.meituan.route.model.UserIntent;
import com.meituan.route.model.UserPreference;
import com.meituan.route.service.UserProfileService;
import com.meituan.route.solver.ConstraintEngine;
import com.meituan.route.solver.PreferenceScorer;
import com.meituan.route.state.SessionStateManager;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

import java.time.Duration;
import java.util.*;
import java.util.stream.Collectors;

/**
 * RoutePlannerOrchestrator — the main orchestrator that coordinates all agents
 * in a multi-agent pipeline: Conversation → Discovery → Planning → Constraint → Explanation.
 *
 * Supports both initial planning and incremental adjustment.
 */
@Service
public class RoutePlannerOrchestrator {

    private static final Logger log = LoggerFactory.getLogger(RoutePlannerOrchestrator.class);

    private final ConversationAgent conversationAgent;
    private final DiscoveryAgent discoveryAgent;
    private final PlanningAgent planningAgent;
    private final ConstraintAgent constraintAgent;
    private final ExplanationAgent explanationAgent;
    private final SessionStateManager sessionManager;
    private final ConstraintEngine constraintEngine;
    private final UserProfileService userProfileService;
    private final PreferenceScorer preferenceScorer;

    public RoutePlannerOrchestrator(ConversationAgent conversationAgent,
                                    DiscoveryAgent discoveryAgent,
                                    PlanningAgent planningAgent,
                                    ConstraintAgent constraintAgent,
                                    ExplanationAgent explanationAgent,
                                    SessionStateManager sessionManager,
                                    ConstraintEngine constraintEngine,
                                    UserProfileService userProfileService,
                                    PreferenceScorer preferenceScorer) {
        this.conversationAgent = conversationAgent;
        this.discoveryAgent = discoveryAgent;
        this.planningAgent = planningAgent;
        this.constraintAgent = constraintAgent;
        this.explanationAgent = explanationAgent;
        this.sessionManager = sessionManager;
        this.constraintEngine = constraintEngine;
        this.userProfileService = userProfileService;
        this.preferenceScorer = preferenceScorer;
    }

    /**
     * Full pipeline: plan a route from natural language query.
     */
    public Mono<PlanResponse> planRoute(String query, String sessionId, String requestCity) {
        return planRoute(query, sessionId, requestCity, null, null);
    }

    /**
     * Full pipeline with optional pre-parsed intent.
     */
    public Mono<PlanResponse> planRoute(String query, String sessionId, String requestCity, UserIntent preParsedIntent) {
        return planRoute(query, sessionId, requestCity, preParsedIntent, null);
    }

    /**
     * Full pipeline with pre-parsed intent + user preference for personalization.
     */
    public Mono<PlanResponse> planRoute(String query, String sessionId, String requestCity,
                                         UserIntent preParsedIntent, String userId) {
        final var t0 = System.nanoTime();
        log.info("Orchestrator: starting route plan for '{}', city={}, preParsedIntent={}, userId={}",
                query, requestCity, preParsedIntent != null, userId);

        // Use pre-parsed intent city > requestCity > default 北京 for speculative discovery
        final var effectiveCity = (preParsedIntent != null && preParsedIntent.city() != null && !preParsedIntent.city().isBlank())
                ? preParsedIntent.city()
                : (requestCity != null && !requestCity.isBlank()) ? requestCity : "北京";

        var broadIntent = DiscoveryAgent.broadIntent(effectiveCity);
        var speculativeDiscovery = discoveryAgent.discover(broadIntent)
                .subscribeOn(Schedulers.boundedElastic())
                .doOnTerminate(() -> logTiming("Discovery(spec)", t0));

        // If intent was already parsed by /api/route/analyze, reuse it — skip duplicate LLM call
        var llmMono = preParsedIntent != null
                ? Mono.fromCallable(() -> {
                    var sid = (sessionId != null && !sessionId.isBlank()) ? sessionId : sessionManager.createSession(userId);
                    var ppCity = preParsedIntent.city();
                    var resolvedPpCity = (ppCity != null && !ppCity.isBlank())
                            ? ppCity
                            : (requestCity != null && !requestCity.isBlank()) ? requestCity : "北京";
                    var intent = resolvedPpCity.equals(ppCity) ? preParsedIntent : preParsedIntent.withCity(resolvedPpCity);
                    log.info("Skipped LLM parse — using pre-parsed intent from analyze step");
                    return new ConversationAgent.ConversationResult(sid, intent, null, null);
                })
                : Mono.defer(() -> {
                    // Resolve user API key before calling LLM
                    return (userId != null && !userId.isBlank()
                            ? userProfileService.resolveApiKey(userId)
                            : Mono.just(new UserProfileService.UserApiKey(null, null)))
                            .flatMap(ak -> conversationAgent.processAsync(query, sessionId, requestCity,
                                    ak.providerName(), ak.apiKey()));
                }).doOnTerminate(() -> logTiming("Conversation", t0));

        // Load user profile + API key in parallel with LLM+Discovery
        var prefMono = (userId != null && !userId.isBlank())
                ? userProfileService.getUserProfile(userId)
                : Mono.just(UserPreference.neutral());
        final var tAfterZip = System.nanoTime();
        return Mono.zip(llmMono, speculativeDiscovery, prefMono)
                .doOnTerminate(() -> logTiming("Phase1(zip)", tAfterZip))
                .flatMap(tuple -> {
                    var convResult = tuple.getT1();
                    var speculative = tuple.getT2();
                    var preference = tuple.getT3();
                    var actualSessionId = convResult.sessionId();

                    var rawIntent = convResult.intent();
                    // Prefer LLM-parsed city when it's specific; only use requestCity as fallback
                    var llmCity = rawIntent.city();
                    var resolvedCity = (llmCity != null && !llmCity.isBlank())
                            ? llmCity
                            : (requestCity != null && !requestCity.isBlank()) ? requestCity : "北京";
                    var intent = resolvedCity.equals(rawIntent.city()) ? rawIntent : rawIntent.withCity(resolvedCity);
                    var city = resolvedCity;

                    // Re-discover when: city mismatch, or intent has district/keywords (broad speculative lacks those filters)
                    var hasSpecificFilters = (intent.district() != null && !intent.district().isBlank())
                            || (intent.keywords() != null && !intent.keywords().isEmpty());
                    var needsRediscovery = !effectiveCity.equals(city) || hasSpecificFilters;
                    final var tDisc = System.nanoTime();
                    var discoveryMono = needsRediscovery
                            ? discoveryAgent.discover(intent).subscribeOn(Schedulers.boundedElastic())
                                    .doOnTerminate(() -> logTiming("Discovery(targeted)", tDisc))
                            : Mono.just(speculative);

                    return discoveryMono
                            .flatMap(discovery -> {
                        // Only filter when reusing broad speculative results; re-discovered results already have filters applied
                        var effectiveDiscovery = (!needsRediscovery && hasSpecificCategories(intent))
                                ? discoveryAgent.filterForIntent(discovery, intent)
                                : discovery;

                        final var tPlan = System.nanoTime();
                        var planResult = planningAgent.plan(effectiveDiscovery, intent, null, preference);
                        logTiming("Planning", tPlan);

                        if (!planResult.hasRoutes()) {
                            return Mono.just(new PlanResponse(actualSessionId, List.of(),
                                    planResult.warning() != null ? planResult.warning() : "无法生成路线方案",
                                    null, "", Map.of(), Map.of(), Map.of(), Map.of()));
                        }

                        sessionManager.addSnapshots(actualSessionId, planResult.routes(), intent);

                        // Constraint analysis and explanation are independent — run in parallel
                        var constraintMono = Mono.fromCallable(() -> {
                            var constraints = constraintEngine.buildConstraints(intent, effectiveDiscovery.candidates());
                            final var tCa = System.nanoTime();
                            var report = constraintAgent.analyze(planResult.routes(), constraints, intent);
                            logTiming("Constraint", tCa);
                            return report;
                        }).subscribeOn(Schedulers.boundedElastic());

                        var explanationMono = Mono.fromCallable(() -> {
                            final var tEx = System.nanoTime();
                            var result = explanationAgent.explain(planResult.routes(), intent);
                            logTiming("Explanation", tEx);
                            return result;
                        }).subscribeOn(Schedulers.boundedElastic());

                        return Mono.zip(constraintMono, explanationMono).map(postResult -> {
                            var constraintReport = postResult.getT1();
                            var explanation = postResult.getT2();
                            var routes = planResult.routes();
                            var warning = constraintReport.allFeasible() ? null : "部分方案存在约束冲突";

                            // Compute preference match data per route
                            var prefMatchTags = new LinkedHashMap<String, List<String>>();
                            var prefScores = new LinkedHashMap<String, Double>();
                            var ugcMatchTags = new LinkedHashMap<String, List<String>>();
                            var ugcSummaries = new LinkedHashMap<String, List<String>>();
                            var isNeutral = preference.userId() == null || "default".equals(preference.userId());
                            if (!isNeutral) {
                                for (var r : routes) {
                                    prefMatchTags.put(r.id(), preferenceScorer.matchedTags(r, preference));
                                    prefScores.put(r.id(), preferenceScorer.normalizedScore(r, preference));
                                    ugcMatchTags.put(r.id(), preferenceScorer.matchedUGCTags(r, preference));
                                    ugcSummaries.put(r.id(), preferenceScorer.matchedUGCSummaries(r, preference));
                                }
                            }

                            logTiming("TOTAL planRoute", t0);
                            return new PlanResponse(
                                    actualSessionId,
                                    routes,
                                    warning,
                                    constraintReport.bestRoute(),
                                    explanation.comparisonHtml(),
                                    prefMatchTags,
                                    prefScores,
                                    ugcMatchTags,
                                    ugcSummaries
                            );
                        });
                    });
                })
                .timeout(Duration.ofSeconds(15));
    }

    private boolean hasSpecificCategories(UserIntent intent) {
        var cats = intent.preferredCategories();
        return cats != null && !cats.isEmpty();
    }

    /**
     * Adjustment pipeline: modify an existing route based on natural language feedback.
     * Runs session lookup + constraint parsing in parallel with the conversation LLM call
     * (Mono.zip), then constraint analysis + explanation in parallel at the tail.
     */
    public Mono<PlanResponse> adjustRoute(String sessionId, String adjustment, String requestCity) {
        return adjustRoute(sessionId, adjustment, requestCity, null);
    }

    public Mono<PlanResponse> adjustRoute(String sessionId, String adjustment, String requestCity, String userId) {
        log.info("Orchestrator: adjusting route for session {}: '{}', city={}, userId={}", sessionId, adjustment, requestCity, userId);

        // Phase 1 (parallel): session lookup + preprocessing  ||  conversation LLM call
        var preprocessMono = Mono.fromCallable(() -> {
            var sessionOpt = sessionManager.getSession(sessionId);
            if (sessionOpt.isEmpty()) {
                return new AdjustmentContext(null, null, null, null, true, false);
            }
            var session = sessionOpt.get();
            var currentRoute = sessionManager.getLatestRoute(sessionId).orElse(null);
            if (currentRoute == null) {
                return new AdjustmentContext(null, null, null, null, false, true);
            }
            var additionalConstraints = constraintAgent.parseAdjustmentConstraints(adjustment);
            int keepCount = sessionManager.resolveAdjustment(adjustment, currentRoute);
            // "少走路"/"更便宜" → don't keep any old POIs — full replan with new constraints
            if (adjustment.contains("少走路") || adjustment.contains("少走")
                    || adjustment.contains("更便宜") || adjustment.contains("便宜")) {
                keepCount = 0;
            }
            var keptPrefix = currentRoute.segments().stream().limit(keepCount).toList();
            return new AdjustmentContext(additionalConstraints, keptPrefix, session, currentRoute, false, false);
        }).subscribeOn(Schedulers.boundedElastic());

        var convMono = Mono.defer(() -> {
            return (userId != null && !userId.isBlank()
                    ? userProfileService.resolveApiKey(userId)
                    : Mono.just(new UserProfileService.UserApiKey(null, null)))
                    .flatMap(ak -> conversationAgent.processAsync(adjustment, sessionId, requestCity,
                            ak.providerName(), ak.apiKey()));
        });
        var prefMono = (userId != null && !userId.isBlank())
                ? userProfileService.getUserProfile(userId)
                : Mono.just(UserPreference.neutral());

        return Mono.zip(preprocessMono, convMono, prefMono).flatMap(tuple -> {
            var ctx = tuple.getT1();
            var convResult = tuple.getT2();
            var preference = tuple.getT3();

            if (ctx.sessionNotFound) {
                return Mono.just(new PlanResponse(sessionId, List.of(), "会话不存在或已过期", null, "", Map.of(), Map.of(), Map.of(), Map.of()));
            }
            if (ctx.fallbackToPlan) {
                return planRoute(adjustment, sessionId, requestCity, null, userId);
            }

            var parsedIntent = (requestCity != null && !requestCity.isBlank())
                    ? convResult.intent().withCity(requestCity)
                    : convResult.intent();
            var mergedIntent = (convResult.previousIntent() != null)
                    ? mergeIntentContext(parsedIntent, convResult.previousIntent())
                    : parsedIntent;
            // "少走路" → force FASTEST goal + WALKING mode to minimize walking distance
            final var intentAfterWalking = adjustment.contains("少走路") || adjustment.contains("少走")
                    ? mergedIntent.withGoal("FASTEST").withTravelMode("WALKING")
                    : mergedIntent;
            // "更便宜"/"便宜一点" → force CHEAPEST goal + reduce budget by ~30%
            final com.meituan.route.model.UserIntent newIntent;
            if (adjustment.contains("更便宜") || adjustment.contains("便宜一点") || adjustment.contains("便宜")) {
                var reducedBudget = intentAfterWalking.budget() > 0
                        ? Math.max(30, intentAfterWalking.budget() * 0.7)
                        : 100; // fallback budget when none was set
                newIntent = intentAfterWalking.withGoal("CHEAPEST")
                        .withBudget((int) reducedBudget);
            } else {
                newIntent = intentAfterWalking;
            }

            return discoveryAgent.discover(newIntent).flatMap(discovery -> {
                var planResult = planningAgent.replan(discovery, newIntent,
                        ctx.keptPrefix, ctx.additionalConstraints, preference);

                if (!planResult.hasRoutes()) {
                    return Mono.just(new PlanResponse(sessionId, List.of(),
                            "调整后无法生成新路线", null, "", Map.of(), Map.of(), Map.of(), Map.of()));
                }

                // Build constraints including adjustment-specific ones
                var constraints = constraintEngine.buildConstraints(newIntent, discovery.candidates());
                if (ctx.additionalConstraints != null) {
                    constraints.addAll(ctx.additionalConstraints);
                }

                // Batch-save snapshots (single DB round-trip)
                sessionManager.addSnapshots(sessionId, planResult.routes(), newIntent);

                // Constraint analysis and explanation are independent — run in parallel
                var constraintMono = Mono.fromCallable(() ->
                    constraintAgent.analyze(planResult.routes(), constraints, newIntent)
                ).subscribeOn(Schedulers.boundedElastic());

                var explanationMono = Mono.fromCallable(() ->
                    explanationAgent.explain(planResult.routes(), newIntent)
                ).subscribeOn(Schedulers.boundedElastic());

                return Mono.zip(constraintMono, explanationMono).map(postResult -> {
                    var constraintReport = postResult.getT1();
                    var explanation = postResult.getT2();
                    var routes = planResult.routes();
                    var prefMatchTags = new LinkedHashMap<String, List<String>>();
                    var prefScores = new LinkedHashMap<String, Double>();
                    var ugcMatchTags = new LinkedHashMap<String, List<String>>();
                    var ugcSummaries = new LinkedHashMap<String, List<String>>();
                    var isNeutral = preference.userId() == null || "default".equals(preference.userId());
                    if (!isNeutral) {
                        for (var r : routes) {
                            prefMatchTags.put(r.id(), preferenceScorer.matchedTags(r, preference));
                            prefScores.put(r.id(), preferenceScorer.normalizedScore(r, preference));
                            ugcMatchTags.put(r.id(), preferenceScorer.matchedUGCTags(r, preference));
                            ugcSummaries.put(r.id(), preferenceScorer.matchedUGCSummaries(r, preference));
                        }
                    }
                    return new PlanResponse(
                            sessionId,
                            routes,
                            constraintReport.allFeasible() ? null : "调整后存在约束冲突",
                            constraintReport.bestRoute(),
                            explanation.comparisonHtml(),
                            prefMatchTags,
                            prefScores,
                            ugcMatchTags,
                            ugcSummaries
                    );
                });
            });
        }).timeout(Duration.ofSeconds(15));
    }

    private record AdjustmentContext(
            List<com.meituan.route.model.Constraint> additionalConstraints,
            List<Route.RouteSegment> keptPrefix,
            SessionStateManager.Session session,
            Route currentRoute,
            boolean sessionNotFound,
            boolean fallbackToPlan
    ) {}

    /**
     * Get comparison data for a session.
     */
    public Mono<CompareResponse> getComparison(String sessionId) {
        return Mono.fromCallable(() -> {
            var sessionOpt = sessionManager.getSession(sessionId);
            if (sessionOpt.isEmpty()) {
                return new CompareResponse(sessionId, List.of(), "会话不存在");
            }

            var allRoutes = sessionManager.getAllRoutes(sessionId);
            var explanation = explanationAgent.explain(allRoutes,
                    sessionOpt.get().currentIntent());
            var groupedByVersion = sessionOpt.get().snapshots().stream()
                    .collect(Collectors.groupingBy(s -> s.version()));

            return new CompareResponse(sessionId, allRoutes, explanation.comparisonHtml());
        });
    }

    private UserIntent mergeIntentContext(UserIntent newIntent, UserIntent previous) {
        var city = (newIntent.city() == null || newIntent.city().isBlank() || newIntent.city().equals("北京"))
                ? previous.city()
                : newIntent.city();
        var district = newIntent.district() != null ? newIntent.district() : previous.district();
        // Merge keywords from previous intent
        var keywords = new java.util.ArrayList<>(newIntent.keywords());
        if (previous.keywords() != null) {
            for (var kw : previous.keywords()) {
                if (!keywords.contains(kw)) keywords.add(kw);
            }
        }
        // Merge preferredCategories from previous intent.
        // When the LLM returns all 5 standard categories for an adjustment query like
        // "少走路", it means no specific category was detected — use the previous
        // intent's categories exclusively. Otherwise, merge both.
        var STANDARD_CATEGORIES = java.util.Set.of("RESTAURANT", "SHOPPING", "ATTRACTION", "ENTERTAINMENT", "CULTURE");
        var newCats = newIntent.preferredCategories() != null ? newIntent.preferredCategories() : java.util.List.<String>of();
        var prevCats = previous.preferredCategories() != null ? previous.preferredCategories() : java.util.List.<String>of();
        var newIsGeneric = newCats.size() >= 4 && newCats.stream().allMatch(STANDARD_CATEGORIES::contains);
        java.util.List<String> categories;
        if (newIsGeneric && !prevCats.isEmpty()) {
            // LLM returned default all-category set — use previous intent's categories
            categories = new java.util.ArrayList<>(prevCats);
        } else if (newCats.isEmpty() && !prevCats.isEmpty()) {
            categories = new java.util.ArrayList<>(prevCats);
        } else {
            categories = new java.util.ArrayList<>(newCats);
            if (!prevCats.isEmpty()) {
                for (var cat : prevCats) {
                    if (!categories.contains(cat)) categories.add(cat);
                }
            }
        }
        // Merge cuisine preference
        var cuisine = newIntent.cuisinePreference() != null ? newIntent.cuisinePreference() : previous.cuisinePreference();
        // Merge special request
        var specialReq = (newIntent.specialRequest() != null && !newIntent.specialRequest().isBlank())
                ? newIntent.specialRequest() : previous.specialRequest();
        // Merge time: adjustment LLM defaults to current time; preserve original if unchanged
        var nowSentinel = java.time.LocalTime.now().withSecond(0).withNano(0);
        var startTime = newIntent.startTime() != null && !newIntent.startTime().equals(nowSentinel)
                ? newIntent.startTime() : previous.startTime();
        var endTime = newIntent.endTime() != null && !newIntent.endTime().equals(java.time.LocalTime.of(22, 0))
                ? newIntent.endTime() : previous.endTime();
        // Merge budget: use adjustment value if specified, otherwise preserve
        var budget = newIntent.budget() > 0 ? newIntent.budget() : previous.budget();
        // Merge rating/queue: preserve from previous unless explicitly changed
        var minRating = newIntent.minRating() > 3.5 ? newIntent.minRating() : previous.minRating();
        var maxQueue = newIntent.maxQueueMinutes() < 30 ? newIntent.maxQueueMinutes() : previous.maxQueueMinutes();
        return new com.meituan.route.model.UserIntent(
                newIntent.rawQuery(), city, district,
                categories, cuisine,
                startTime, endTime, budget,
                newIntent.partySize(), minRating, maxQueue,
                newIntent.travelMode(), newIntent.optimizationGoal(),
                specialReq, keywords, newIntent.sessionId()
        );
    }

    private static void logTiming(String step, long startNanos) {
        var elapsed = (System.nanoTime() - startNanos) / 1_000_000.0;
        log.info("[TIMING] {} took {}ms", step, Math.round(elapsed));
    }

    // Response types
    public record PlanResponse(
            String sessionId,
            List<Route> routes,
            String warning,
            Route recommendedRoute,
            String explanation,
            Map<String, List<String>> preferenceMatchTags,
            Map<String, Double> preferenceScores,
            Map<String, List<String>> ugcMatchTags,       // UGC tags matched per route (from real user reviews)
            Map<String, List<String>> ugcSummaries         // UGC summary snippets per route
    ) {}

    public record CompareResponse(
            String sessionId,
            List<Route> routes,
            String comparisonHtml
    ) {}
}
