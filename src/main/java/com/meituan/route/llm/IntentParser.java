package com.meituan.route.llm;

import com.meituan.route.model.IntentAnalysisResult;
import com.meituan.route.model.UserIntent;
import dev.langchain4j.model.chat.ChatLanguageModel;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

import java.time.LocalTime;
import java.util.*;
import java.util.regex.Pattern;

/**
 * Parses natural language user queries into structured UserIntent.
 *
 * Two-tier architecture:
 *   Tier 1: LangChain4j LLM (DeepSeek) for accurate semantic parsing
 *   Tier 2: Rule-based fallback when LLM is unavailable
 */
@Component
public class IntentParser {


    private static final Logger log = LoggerFactory.getLogger(IntentParser.class);

    private final ChatLanguageModel chatModel;
    private final boolean llmAvailable;
    private final boolean mockProfile;

    private static final Pattern BUDGET_PATTERN = Pattern.compile("预算(\\d+)");
    private static final Pattern RATING_PATTERN = Pattern.compile("评分[以至少高于大于等于]*([\\d.]+)");

    private static final Map<String, String> TIME_KEYWORDS = Map.of(
            "早上", "08:00", "上午", "09:00", "中午", "12:00",
            "下午", "14:00", "傍晚", "17:00", "晚上", "18:00", "夜间", "20:00"
    );

    private static final Map<String, String> CATEGORY_MAP = Map.ofEntries(
            Map.entry("逛街", "SHOPPING"), Map.entry("购物", "SHOPPING"), Map.entry("商场", "SHOPPING"),
            Map.entry("吃", "RESTAURANT"), Map.entry("餐厅", "RESTAURANT"), Map.entry("美食", "RESTAURANT"),
            Map.entry("日料", "RESTAURANT"), Map.entry("火锅", "RESTAURANT"), Map.entry("烤鸭", "RESTAURANT"),
            Map.entry("面", "RESTAURANT"), Map.entry("简餐", "RESTAURANT"), Map.entry("烤肉", "RESTAURANT"),
            Map.entry("烧烤", "RESTAURANT"), Map.entry("小吃", "RESTAURANT"), Map.entry("咖啡", "RESTAURANT"),
            Map.entry("甜品", "RESTAURANT"), Map.entry("烘焙", "RESTAURANT"), Map.entry("面包", "RESTAURANT"),
            Map.entry("西餐", "RESTAURANT"), Map.entry("法餐", "RESTAURANT"), Map.entry("意式", "RESTAURANT"),
            Map.entry("粤菜", "RESTAURANT"), Map.entry("川菜", "RESTAURANT"), Map.entry("湘菜", "RESTAURANT"),
            Map.entry("本帮菜", "RESTAURANT"), Map.entry("上海菜", "RESTAURANT"), Map.entry("北京菜", "RESTAURANT"),
            Map.entry("云南菜", "RESTAURANT"), Map.entry("喝茶", "RESTAURANT"), Map.entry("奶茶", "RESTAURANT"),
            Map.entry("轻食", "RESTAURANT"), Map.entry("沙拉", "RESTAURANT"),
            Map.entry("景点", "ATTRACTION"), Map.entry("玩", "ATTRACTION"), Map.entry("公园", "ATTRACTION"),
            Map.entry("园林", "ATTRACTION"), Map.entry("爬山", "ATTRACTION"), Map.entry("登山", "ATTRACTION"),
            Map.entry("电影", "ENTERTAINMENT"), Map.entry("KTV", "ENTERTAINMENT"), Map.entry("唱歌", "ENTERTAINMENT"),
            Map.entry("演出", "ENTERTAINMENT"), Map.entry("livehouse", "ENTERTAINMENT"), Map.entry("LiveHouse", "ENTERTAINMENT"),
            Map.entry("酒吧", "RESTAURANT"), Map.entry("喝酒", "RESTAURANT"), Map.entry("喝一", "RESTAURANT"),
            Map.entry("喝杯", "RESTAURANT"), Map.entry("喝口", "RESTAURANT"), Map.entry("小酌", "RESTAURANT"),
            Map.entry("精酿", "RESTAURANT"), Map.entry("居酒屋", "RESTAURANT"), Map.entry("娱乐", "RESTAURANT"),
            Map.entry("文化", "CULTURE"), Map.entry("博物馆", "CULTURE"), Map.entry("书店", "CULTURE"),
            Map.entry("艺术", "CULTURE"), Map.entry("美术馆", "CULTURE"), Map.entry("画廊", "CULTURE"),
            Map.entry("展览", "CULTURE"), Map.entry("看展", "CULTURE"), Map.entry("创意园", "CULTURE"),
            Map.entry("互动展览", "CULTURE"), Map.entry("互动", "ENTERTAINMENT"), Map.entry("儿童", "ENTERTAINMENT"),
            Map.entry("亲子", "ENTERTAINMENT"), Map.entry("遛娃", "ENTERTAINMENT"), Map.entry("乐园", "ENTERTAINMENT"),
            Map.entry("游乐", "ENTERTAINMENT"), Map.entry("动物园", "ATTRACTION"), Map.entry("植物园", "ATTRACTION"),
            Map.entry("水族馆", "ATTRACTION"), Map.entry("海洋馆", "ATTRACTION"), Map.entry("科技馆", "CULTURE"),
            Map.entry("自然博物馆", "CULTURE"), Map.entry("天文馆", "CULTURE"), Map.entry("图书馆", "CULTURE")
    );

    private static final Map<String, String> DISTRICT_MAP = Map.ofEntries(
            Map.entry("三里屯", "三里屯"), Map.entry("国贸", "国贸"),
            Map.entry("王府井", "王府井"), Map.entry("前门", "前门"),
            Map.entry("东城", "东城"), Map.entry("西城", "西城"),
            Map.entry("海淀", "海淀"), Map.entry("朝阳", "朝阳"),
            Map.entry("外滩", "外滩"), Map.entry("陆家嘴", "陆家嘴"),
            Map.entry("新天地", "新天地"), Map.entry("南京路", "南京路"),
            Map.entry("静安", "静安区"), Map.entry("静安寺", "静安区"),
            Map.entry("徐汇", "徐汇区"), Map.entry("浦东", "浦东新区"),
            Map.entry("武康路", "武康路"), Map.entry("黄浦", "黄浦区"),
            Map.entry("田子坊", "田子坊"), Map.entry("豫园", "豫园"),
            Map.entry("虹桥", "虹桥"), Map.entry("人民广场", "人民广场"),
            Map.entry("长宁", "长宁区"), Map.entry("普陀", "普陀区"),
            Map.entry("杨浦", "杨浦区"), Map.entry("闵行", "闵行区"),
            Map.entry("宝山", "宝山区"), Map.entry("嘉定", "嘉定区"),
            Map.entry("松江", "松江区"), Map.entry("奉贤", "奉贤区"),
            Map.entry("青浦", "青浦区"), Map.entry("崇明", "崇明区"),
            Map.entry("丰台", "丰台区"), Map.entry("通州", "通州区"),
            Map.entry("大兴", "大兴区"), Map.entry("昌平", "昌平区"),
            Map.entry("石景山", "石景山区"), Map.entry("顺义", "顺义区"),
            Map.entry("房山", "房山区"), Map.entry("门头沟", "门头沟区"),
            Map.entry("平谷", "平谷区"), Map.entry("密云", "密云区"),
            Map.entry("怀柔", "怀柔区"), Map.entry("延庆", "延庆区")
    );

    private final DynamicLLMProvider llmProvider;
    private final com.meituan.route.security.LLMAuditLogger auditLogger;
    private final com.meituan.route.security.LLMRateLimiter rateLimiter;

    public IntentParser(Optional<ChatLanguageModel> chatModel, Environment env,
                        DynamicLLMProvider llmProvider,
                        com.meituan.route.security.LLMAuditLogger auditLogger,
                        com.meituan.route.security.LLMRateLimiter rateLimiter) {
        this.chatModel = chatModel.orElse(null);
        this.llmProvider = llmProvider;
        this.auditLogger = auditLogger;
        this.rateLimiter = rateLimiter;
        this.mockProfile = java.util.Arrays.asList(env.getActiveProfiles()).contains("mock");
        this.llmAvailable = this.chatModel != null;
        log.info("IntentParser initialized (LLM: {}, mock: {})", llmAvailable ? "enabled" : "disabled", mockProfile);
    }

    /**
     * Parse a natural language query into a structured UserIntent.
     */
    public UserIntent parse(String query, String sessionId) {
        return parse(query, sessionId, null);
    }

    private UserIntent parseWithLLM(String query, String sessionId, String cityHint) {
        return parseWithLLM(query, sessionId, cityHint, null, null, null);
    }

    private UserIntent parseWithLLM(String query, String sessionId, String cityHint, UserIntent previousIntent) {
        return parseWithLLM(query, sessionId, cityHint, previousIntent, null, null);
    }

    private UserIntent parseWithLLM(String query, String sessionId, String cityHint,
                                     UserIntent previousIntent, String userProvider, String userApiKey) {
        var exampleCity = (cityHint != null && !cityHint.isBlank()) ? cityHint : "北京";
        var cityContext = (cityHint != null && !cityHint.isBlank())
                ? "当前用户所在城市: " + cityHint + "。若查询未明确提到城市，city字段使用此城市。\n"
                : "";

        var previousContext = "";
        if (previousIntent != null) {
            var sb = new StringBuilder();
            sb.append("\n上一次理解的需求（请保持这些关键约束，除非用户明确要求更改）:\n");
            sb.append("- 城市: ").append(previousIntent.city()).append("\n");
            if (previousIntent.district() != null && !previousIntent.district().isBlank())
                sb.append("- 区域: ").append(previousIntent.district()).append("\n");
            if (previousIntent.budget() > 0)
                sb.append("- 预算: 人均¥").append((int) previousIntent.budget()).append("\n");
            if (previousIntent.preferredCategories() != null && !previousIntent.preferredCategories().isEmpty())
                sb.append("- 分类: ").append(String.join("、", previousIntent.preferredCategories())).append("\n");
            if (previousIntent.keywords() != null && !previousIntent.keywords().isEmpty())
                sb.append("- 关键词: ").append(String.join("、", previousIntent.keywords())).append("\n");
            if (previousIntent.specialRequest() != null && !previousIntent.specialRequest().isBlank())
                sb.append("- 特殊要求: ").append(previousIntent.specialRequest()).append("\n");
            if (previousIntent.cuisinePreference() != null && !previousIntent.cuisinePreference().isBlank())
                sb.append("- 菜系偏好: ").append(previousIntent.cuisinePreference()).append("\n");
            previousContext = sb.toString();
        }

        var nowStr = LocalTime.now().format(java.time.format.DateTimeFormatter.ofPattern("HH:mm"));
        var prompt = (cityContext + """
从查询提取JSON（只返回JSON）：
查询: "%s"%s
字段: city(北京/上海), district(商圈/null), categories(RESTAURANT/SHOPPING/ATTRACTION/ENTERTAINMENT/CULTURE数组), cuisine(菜系/null), startTime(HH:MM,默认当前时间%s), endTime(HH:MM,默认22:00), budget(数字,0=不限), partySize(人数,默认2), minRating(默认3.5), maxQueue(排队分钟,0=不排队,默认30), travelMode(WALKING/DRIVING), goal(BEST_EXPERIENCE/FASTEST/CHEAPEST), keywords(数组), specialRequest(特殊要求/null)
示例: {"city":"%s","district":null,"categories":["RESTAURANT"],"cuisine":null,"startTime":"%s","endTime":"22:00","budget":150,"partySize":2,"minRating":4.0,"maxQueue":15,"travelMode":"WALKING","goal":"BEST_EXPERIENCE","keywords":["拍照"],"specialRequest":null}
""".formatted(query, previousContext, nowStr, exampleCity, nowStr));

        // Rate limiting: prevent API abuse and cost explosion
        var userId = sessionId != null ? sessionId : "anonymous";
        if (!rateLimiter.tryAcquire(userId, "internal")) {
            log.warn("IntentParser: rate limited for session {}", userId);
            throw new RuntimeException("请求过于频繁，请稍后再试 (rate limited)");
        }

        // Use user's own model + API key if provided, otherwise system default
        var model = (userApiKey != null && !userApiKey.isBlank())
                ? llmProvider.getModel(userProvider, userApiKey)
                : chatModel;
        var provider = (userProvider != null && !userProvider.isBlank())
                ? userProvider : llmProvider.getDefaultProviderId();
        int estimatedInput = auditLogger.estimateTokens(prompt);
        long t0 = System.currentTimeMillis();
        var json = model.chat(prompt);
        long latency = System.currentTimeMillis() - t0;
        rateLimiter.release();

        // Audit log: track every LLM call for cost attribution
        int estimatedOutput = auditLogger.estimateTokens(json);
        auditLogger.record(userId, provider, "deepseek-chat",
                estimatedInput, estimatedOutput, latency);

        // Parse the JSON response
        return parseLLMResponse(json, query, sessionId);
    }

    /**
     * Reactive variant: offloads the blocking LLM call to boundedElastic so the
     * event loop is never blocked, even under high concurrency. Use this from
     * reactive chains to avoid thread-pool exhaustion.
     */
    public Mono<UserIntent> parseAsync(String query, String sessionId) {
        return parseAsync(query, sessionId, null);
    }

    public Mono<UserIntent> parseAsync(String query, String sessionId, String cityHint) {
        return parseAsync(query, sessionId, cityHint, null);
    }

    public Mono<UserIntent> parseAsync(String query, String sessionId, String cityHint, UserIntent previousIntent) {
        return parseAsync(query, sessionId, cityHint, previousIntent, null, null);
    }

    /** Parse with optional user-provided LLM API key (from registration). */
    public Mono<UserIntent> parseAsync(String query, String sessionId, String cityHint,
                                        UserIntent previousIntent, String userProvider, String userApiKey) {
        if (llmAvailable) {
            return Mono.fromCallable(() -> parseWithLLM(query, sessionId, cityHint, previousIntent, userProvider, userApiKey))
                    .subscribeOn(Schedulers.boundedElastic())
                    .onErrorResume(e -> {
                        log.warn("LLM parsing failed, falling back to rules: {}", e.getMessage());
                        return Mono.fromCallable(() -> parseWithRules(query, sessionId))
                                .subscribeOn(Schedulers.boundedElastic());
                    });
        }
        return Mono.fromCallable(() -> parseWithRules(query, sessionId));
    }

    private UserIntent parse(String query, String sessionId, String cityHint) {
        if (query == null || query.isBlank()) {
            throw new IllegalArgumentException("Query cannot be empty");
        }

        // Tier 1: Try LLM-based parsing
        if (llmAvailable) {
            try {
                log.info(">>> Using LLM to parse query: {}", query.substring(0, Math.min(60, query.length())));
                return parseWithLLM(query, sessionId, cityHint);
            } catch (Exception e) {
                log.warn("LLM intent parsing failed, falling back to rules: {}", e.getMessage());
            }
        } else {
            log.info(">>> LLM unavailable, using rule-based parsing for: {}", query.substring(0, Math.min(60, query.length())));
        }

        // Tier 2: Rule-based fallback
        return parseWithRules(query, sessionId);
    }

    /**
     * Parse query into intent AND analyze completeness for requirement completion.
     * Returns stage (complete/assumption/followup/conflict), missing fields,
     * and generated followup questions.
     */
    public IntentAnalysisResult analyzeWithCompleteness(String query, String sessionId) {
        return analyzeWithCompleteness(query, sessionId, null);
    }

    /**
     * Analyze query with a city hint. When the query doesn't mention a city,
     * the hint is used as default instead of returning null.
     */
    public IntentAnalysisResult analyzeWithCompleteness(String query, String sessionId, String cityHint) {
        var intent = parse(query, sessionId, cityHint);
        // Resolve city: when query explicitly mentions a city, use it;
        // otherwise fall back to the user's selected city (overrides LLM default "北京")
        var detectedCity = detectCity(query);
        if (detectedCity != null && !detectedCity.equals(intent.city())) {
            intent = intent.withCity(detectedCity);
        } else if (detectedCity == null && cityHint != null && !cityHint.isBlank()) {
            intent = intent.withCity(cityHint);
        }
        return assessCompleteness(intent);
    }

    /**
     * Assess how complete the parsed intent is and generate followup questions.
     */
    private IntentAnalysisResult assessCompleteness(UserIntent intent) {
        // Check key field presence
        boolean hasCategories = intent.preferredCategories() != null && !intent.preferredCategories().isEmpty();
        boolean hasDistrict = intent.district() != null && !intent.district().isBlank();
        boolean hasCuisine = intent.cuisinePreference() != null && !intent.cuisinePreference().isBlank();
        boolean hasBudget = intent.budget() > 0;
        boolean hasKeywords = intent.keywords() != null && !intent.keywords().isEmpty();
        boolean hasSpecial = intent.specialRequest() != null && !intent.specialRequest().isBlank();
        boolean hasTime = intent.startTime() != null;

        var missing = new java.util.ArrayList<String>();
        if (!hasCategories) missing.add("categories");
        // District is optional — only ask when user gave no categories either
        if (!hasDistrict && !hasCategories) missing.add("district");
        if (!hasBudget) missing.add("budget");
        if (!hasKeywords && !hasSpecial && !hasCuisine) missing.add("preferences");

        int filled = (hasCategories ? 1 : 0) + (hasDistrict ? 1 : 0)
                + (hasBudget ? 1 : 0) + (hasKeywords || hasSpecial || hasCuisine ? 1 : 0);
        // When categories are present but district is missing, still generate routes (city-wide search)
        if (hasCategories && !hasDistrict) filled = Math.max(filled, 2);

        // Detect conflicts: high demand + low budget
        boolean highDemand = (hasKeywords && intent.keywords().stream().anyMatch(
                k -> k.contains("拍照") || k.contains("网红") || k.contains("氛围")))
                || (hasSpecial && (intent.specialRequest().contains("氛围") || intent.specialRequest().contains("格调")));
        boolean lowBudget = hasBudget && intent.budget() < 80;
        boolean noQueue = intent.maxQueueMinutes() > 0 && intent.maxQueueMinutes() <= 10;
        boolean highRating = intent.minRating() >= 4.0;
        int conflictCount = (highDemand ? 1 : 0) + (lowBudget ? 1 : 0) + (noQueue ? 1 : 0) + (highRating ? 1 : 0);

        String stage;
        List<IntentAnalysisResult.Conflict> conflicts = List.of();
        List<IntentAnalysisResult.FollowupQuestion> questions = List.of();

        if (conflictCount >= 3) {
            stage = "conflict";
            conflicts = buildConflicts(highDemand, lowBudget, noQueue, highRating);
        } else if (filled >= 3 && hasCategories) {
            stage = "complete";
        } else if (filled >= 2) {
            stage = "assumption";
            questions = buildFollowupQuestions(missing);
        } else {
            stage = "followup";
            questions = buildFollowupQuestions(missing);
        }

        var summary = buildSummary(intent, stage);
        return new IntentAnalysisResult(stage, intent, missing, questions, conflicts, summary);
    }

    private List<IntentAnalysisResult.Conflict> buildConflicts(boolean highDemand, boolean lowBudget, boolean noQueue, boolean highRating) {
        var list = new java.util.ArrayList<IntentAnalysisResult.Conflict>();
        if (highDemand) list.add(new IntentAnalysisResult.Conflict("vibe", "氛围感", "安静、有格调，往往人均偏高"));
        if (lowBudget) list.add(new IntentAnalysisResult.Conflict("budget", "预算低", "人均 80 元内"));
        if (noQueue) list.add(new IntentAnalysisResult.Conflict("noqueue", "不排队", "热门店通常需要等位"));
        if (highRating) list.add(new IntentAnalysisResult.Conflict("rating", "高评分", "4.0以上高分店较热门"));
        return list;
    }

    private List<IntentAnalysisResult.FollowupQuestion> buildFollowupQuestions(List<String> missing) {
        var qs = new java.util.ArrayList<IntentAnalysisResult.FollowupQuestion>();
        for (var field : missing) {
            switch (field) {
                case "categories" -> qs.add(new IntentAnalysisResult.FollowupQuestion(
                        "scene", "你更想规划哪类路线？",
                        List.of("朋友聚会", "情侣约会", "一个人放松", "亲子遛娃")));
                case "district" -> qs.add(new IntentAnalysisResult.FollowupQuestion(
                        "place", "想在哪附近？",
                        List.of("当前位置附近", "地铁站附近", "指定商圈", "输入地点")));
                case "budget" -> qs.add(new IntentAnalysisResult.FollowupQuestion(
                        "budget", "人均预算大概多少？",
                        List.of("¥80 以内", "¥150 以内", "¥200 以内", "不设上限")));
                case "preferences" -> qs.add(new IntentAnalysisResult.FollowupQuestion(
                        "mood", "更想要什么体验？",
                        List.of("吃饭聊天", "拍照出片", "安静放松", "随便逛逛")));
            }
        }
        return qs;
    }

    private String buildSummary(UserIntent intent, String stage) {
        var sb = new StringBuilder();
        var cats = intent.preferredCategories();
        if (cats != null && !cats.isEmpty()) {
            var names = cats.stream().map(this::categoryName).toList();
            sb.append(String.join("+", names));
        } else {
            sb.append("综合");
        }
        if (intent.district() != null && !intent.district().isBlank()) {
            sb.append(" · ").append(intent.district());
        }
        if (intent.budget() > 0) {
            sb.append(" · 人均¥").append((int) intent.budget());
        }
        if (intent.keywords() != null && !intent.keywords().isEmpty()) {
            sb.append(" · ").append(String.join("、", intent.keywords()));
        }
        return sb.toString();
    }

    private String categoryName(String cat) {
        return switch (cat) {
            case "RESTAURANT" -> "美食";
            case "SHOPPING" -> "购物";
            case "ATTRACTION" -> "景点";
            case "ENTERTAINMENT" -> "娱乐";
            case "CULTURE" -> "文化";
            default -> cat;
        };
    }

    private UserIntent parseLLMResponse(String json, String originalQuery, String sessionId) {
        // Default values
        var city = "北京";
        String district = null;
        List<String> categories = new ArrayList<>();
        String cuisine = null;
        var startTime = LocalTime.now().withSecond(0).withNano(0);
        var endTime = LocalTime.of(22, 0);
        double budget = 0;
        int partySize = 2;
        double minRating = 3.5;
        int maxQueue = 30;
        var travelMode = "WALKING";
        var goal = "BEST_EXPERIENCE";
        List<String> keywords = new ArrayList<>();
        String specialRequest = null;

        try {
            // Basic JSON parsing without Jackson dependency conflicts
            json = json.replaceAll("(?s)^```json\\s*", "").replaceAll("(?s)\\s*```$", "");
            json = json.replaceAll("(?s)^```\\s*", "").replaceAll("(?s)\\s*```$", "");

            if (json.contains("\"city\"")) city = extractString(json, "city", city);
            if (json.contains("\"district\"")) district = extractStringOrNull(json, "district");
            if (json.contains("\"cuisine\"")) cuisine = extractStringOrNull(json, "cuisine");
            if (json.contains("\"startTime\"")) {
                var defaultTimeStr = LocalTime.now().format(java.time.format.DateTimeFormatter.ofPattern("HH:mm"));
                var st = extractString(json, "startTime", defaultTimeStr);
                try { startTime = LocalTime.parse(st); } catch (Exception ignored) {}
            }
            if (json.contains("\"endTime\"")) {
                var et = extractString(json, "endTime", "22:00");
                try { endTime = LocalTime.parse(et); } catch (Exception ignored) {}
            }
            if (json.contains("\"budget\"")) budget = extractDouble(json, "budget", 0);
            if (json.contains("\"partySize\"")) partySize = (int) extractDouble(json, "partySize", 2);
            if (json.contains("\"minRating\"")) minRating = extractDouble(json, "minRating", 3.5);
            if (json.contains("\"maxQueue\"")) maxQueue = (int) extractDouble(json, "maxQueue", 30);
            if (json.contains("\"travelMode\"")) travelMode = extractString(json, "travelMode", "WALKING");
            if (json.contains("\"goal\"")) goal = extractString(json, "goal", "BEST_EXPERIENCE");
            if (json.contains("\"categories\"")) categories = extractArray(json, "categories");
            if (json.contains("\"keywords\"")) keywords = extractArray(json, "keywords");
            if (json.contains("\"specialRequest\"")) specialRequest = extractStringOrNull(json, "specialRequest");
        } catch (Exception e) {
            log.warn("Failed to parse LLM JSON response, falling back: {}", e.getMessage());
            return parseWithRules(originalQuery, sessionId);
        }

        // When district is a landmark name, map to real district and add landmark to keywords
        if (district != null && LANDMARK_NAMES.contains(district)) {
            if (!keywords.contains(district)) keywords.add(district);
            district = LANDMARK_TO_DISTRICT.getOrDefault(district, district);
        }

        // When a keyword IS a landmark name but district is null, derive district from keyword
        if (district == null && keywords != null) {
            for (var kw : keywords) {
                if (LANDMARK_NAMES.contains(kw)) {
                    district = LANDMARK_TO_DISTRICT.get(kw);
                    break;
                }
            }
        }

        // Rule-based district fallback: when LLM misses district, detect from original query
        if (district == null) {
            district = detectDistrict(originalQuery);
            if (district != null) {
                log.info("IntentParser: district detected by rule fallback: '{}'", district);
            }
        }

        // Rule-based city detection as safety net: when LLM misses "上海" in query
        var ruleCity = detectCity(originalQuery);
        if (ruleCity != null && !ruleCity.equals(city)) {
            log.info("IntentParser: city corrected by rule from '{}' → '{}'", city, ruleCity);
            city = ruleCity;
        }

        // Post-process: replace ENTERTAINMENT with RESTAURANT — all bar/izakaya/drink
        // POIs in the mock data are RESTAURANT-category, not ENTERTAINMENT.
        if (categories.contains("ENTERTAINMENT")) {
            categories = new ArrayList<>(categories);
            categories.remove("ENTERTAINMENT");
            if (!categories.contains("RESTAURANT")) {
                categories.add("RESTAURANT");
            }
        }

        // Post-process: "人均 X" → per-person budget → convert to total budget
        // LLM returns budget=X (per-person value), but ConstraintEngine treats it as total.
        // Multiply by partySize so hard budget constraint works correctly.
        if (originalQuery != null && originalQuery.contains("人均") && budget > 0) {
            var totalBudget = budget * partySize;
            log.info("IntentParser: '人均' detected — converting budget {} → {} (×{} people)",
                    budget, totalBudget, partySize);
            budget = totalBudget;
        }

        return new UserIntent(originalQuery, city, district, categories, cuisine,
                startTime, endTime, budget, partySize, minRating,
                maxQueue, travelMode, goal, specialRequest, keywords, sessionId);
    }

    // ──────────────────────────────────────────────
    // Tier 2: Rule-based fallback
    // ──────────────────────────────────────────────

    private UserIntent parseWithRules(String query, String sessionId) {
        var city = detectCity(query);
        var district = detectDistrict(query);
        var categories = detectCategories(query);
        var cuisine = detectCuisine(query);
        var times = detectTimeRange(query);
        var budget = detectBudget(query);
        var minRating = detectRating(query);
        var maxQueue = detectQueueTolerance(query);
        var travelMode = detectTravelMode(query);
        var goal = detectGoal(query, categories);
        var keywords = extractKeywords(query);

        // When district is a landmark name, map to real district and add landmark to keywords
        if (district != null && LANDMARK_NAMES.contains(district)) {
            if (!keywords.contains(district)) keywords.add(district);
            district = LANDMARK_TO_DISTRICT.getOrDefault(district, district);
        }

        return new UserIntent(
                query, city, district, categories, cuisine,
                times[0], times[1], budget, 2, minRating,
                maxQueue, travelMode, goal, null, keywords, sessionId
        );
    }

    // Landmark/POI names that appear in DISTRICT_MAP but aren't real district names
    private static final Set<String> LANDMARK_NAMES = Set.of(
            "武康路", "外滩", "陆家嘴", "新天地", "南京路", "静安寺",
            "田子坊", "豫园", "虹桥", "人民广场", "三里屯", "国贸",
            "王府井", "前门"
    );

    // Map landmark names to their actual enclosing districts for geographic filtering
    private static final Map<String, String> LANDMARK_TO_DISTRICT = Map.ofEntries(
            Map.entry("武康路", "徐汇区"), Map.entry("外滩", "黄浦区"),
            Map.entry("新天地", "黄浦区"), Map.entry("田子坊", "黄浦区"),
            Map.entry("豫园", "黄浦区"), Map.entry("人民广场", "黄浦区"),
            Map.entry("南京路", "黄浦区"), Map.entry("静安寺", "静安区"),
            Map.entry("静安", "静安区"), Map.entry("陆家嘴", "浦东新区"),
            Map.entry("虹桥", "闵行区"), Map.entry("三里屯", "朝阳区"),
            Map.entry("国贸", "朝阳区"), Map.entry("王府井", "东城区"),
            Map.entry("前门", "东城区")
    );

    private String detectCity(String query) {
        if (query.contains("上海") || query.contains("外滩") || query.contains("陆家嘴")
                || query.contains("新天地") || query.contains("浦东")
                || query.contains("武康路") || query.contains("静安寺") || query.contains("静安")
                || query.contains("南京路") || query.contains("徐汇") || query.contains("田子坊")
                || query.contains("豫园") || query.contains("虹桥")
                || query.contains("长宁") || query.contains("普陀") || query.contains("杨浦")
                || query.contains("闵行") || query.contains("宝山") || query.contains("嘉定")
                || query.contains("松江") || query.contains("奉贤") || query.contains("青浦")
                || query.contains("崇明") || query.contains("黄浦")) return "上海";
        if (query.contains("北京") || query.contains("三里屯") || query.contains("国贸")
                || query.contains("王府井") || query.contains("前门") || query.contains("故宫")
                || query.contains("颐和园") || query.contains("天安门") || query.contains("天坛")
                || query.contains("长城") || query.contains("北海公园") || query.contains("雍和宫")
                || query.contains("西单") || query.contains("东城") || query.contains("西城")
                || query.contains("海淀") || query.contains("朝阳") || query.contains("丰台")
                || query.contains("东四") || query.contains("南锣鼓巷") || query.contains("什刹海")
                || query.contains("鸟巢") || query.contains("水立方") || query.contains("圆明园")
                || query.contains("798") || query.contains("潘家园") || query.contains("大栅栏")) return "北京";
        return null; // no city detected — let fallback chain use caller-provided city
    }

    private String detectDistrict(String query) {
        return DISTRICT_MAP.entrySet().stream()
                .filter(e -> query.contains(e.getKey()))
                .map(Map.Entry::getValue)
                .findFirst()
                .orElse(null);
    }

    private List<String> detectCategories(String query) {
        var cats = new LinkedHashSet<String>();
        CATEGORY_MAP.forEach((k, v) -> { if (query.contains(k)) cats.add(v); });
        if (cats.isEmpty() && (query.contains("去") || query.contains("到") || query.contains("逛"))) {
            cats.add("ATTRACTION");
            cats.add("RESTAURANT");
        }
        return new ArrayList<>(cats);
    }

    private String detectCuisine(String query) {
        var m = Pattern.compile("(日料|火锅|烤鸭|西餐|川菜|湘菜|云南菜|上海菜|北京菜|粤菜|咖啡|奶茶|甜品)").matcher(query);
        return m.find() ? m.group(1) : null;
    }

    private LocalTime[] detectTimeRange(String query) {
        var start = LocalTime.of(14, 0);
        var end = LocalTime.of(21, 0);
        for (var e : TIME_KEYWORDS.entrySet()) {
            if (query.contains(e.getKey())) {
                start = LocalTime.parse(e.getValue());
                break;
            }
        }
        if (start.isBefore(LocalTime.of(12, 0))) end = LocalTime.of(17, 0);
        else if (start.isBefore(LocalTime.of(17, 0))) end = LocalTime.of(22, 0);
        return new LocalTime[]{start, end};
    }

    private double detectBudget(String query) {
        var m = BUDGET_PATTERN.matcher(query);
        return m.find() ? Double.parseDouble(m.group(1)) : 0;
    }

    private double detectRating(String query) {
        var m = RATING_PATTERN.matcher(query);
        return m.find() ? Double.parseDouble(m.group(1)) : 3.5;
    }

    private int detectQueueTolerance(String query) {
        if (query.contains("不排队") || query.contains("少排队")) return 10;
        if (query.contains("快") || query.contains("效率")) return 15;
        return 30;
    }

    private String detectTravelMode(String query) {
        if (query.contains("开车") || query.contains("驾车") || query.contains("滴滴")) return "DRIVING";
        return "WALKING";
    }

    private String detectGoal(String query, List<String> categories) {
        if (query.contains("省钱") || query.contains("便宜")) return "CHEAPEST";
        if (query.contains("省时") || query.contains("快")) return "FASTEST";
        return "BEST_EXPERIENCE";
    }

    private List<String> extractKeywords(String query) {
        var kw = new ArrayList<String>();
        if (query.contains("拍照")) kw.add("拍照好看");
        if (query.contains("约会")) kw.add("约会");
        if (query.contains("亲子") || query.contains("带娃") || query.contains("遛娃")) kw.add("亲子");
        if (query.contains("网红")) kw.add("网红");
        if (query.contains("互动展览") || query.contains("互动")) kw.add("互动展览");
        if (query.contains("科技馆") || query.contains("科学")) kw.add("科技馆");
        if (query.contains("动物") || query.contains("水族")) kw.add("动物园");
        if (query.contains("乐园") || query.contains("游乐")) kw.add("乐园");
        if (query.contains("安静")) kw.add("安静");
        if (query.contains("放松") || query.contains("发呆") || query.contains("放空")) kw.add("放松");
        if (query.contains("喝酒") || query.contains("喝一") || query.contains("酒吧") || query.contains("小酌")) kw.add("喝酒");
        if (query.contains("美食") || query.contains("好吃")) kw.add("美食");
        if (query.contains("面") && !query.contains("前面")) kw.add("面食");
        if (query.contains("火锅")) kw.add("火锅");
        if (query.contains("咖啡")) kw.add("咖啡");
        return kw;
    }

    // ──────────────────────────────────────────────
    // JSON 解析辅助
    // ──────────────────────────────────────────────

    private String extractString(String json, String key, String defaultValue) {
        var v = extractStringOrNull(json, key);
        return v != null ? v : defaultValue;
    }

    private String extractStringOrNull(String json, String key) {
        var p = "\"" + key + "\"\\s*:\\s*\"";
        var m = Pattern.compile(p + "(.*?)\"").matcher(json);
        if (m.find()) {
            var val = m.group(1).replace("\\\"", "\"").replace("\\n", "\n");
            return val.equals("null") ? null : val;
        }
        return null;
    }

    private double extractDouble(String json, String key, double defaultValue) {
        var p = Pattern.compile("\"" + key + "\"\\s*:\\s*([\\d.]+)");
        var m = p.matcher(json);
        return m.find() ? Double.parseDouble(m.group(1)) : defaultValue;
    }

    private List<String> extractArray(String json, String key) {
        var p = Pattern.compile("\"" + key + "\"\\s*:\\s*\\[(.*?)\\]");
        var m = p.matcher(json);
        if (m.find()) {
            var content = m.group(1);
            var items = new ArrayList<String>();
            var itemM = Pattern.compile("\"(.*?)\"").matcher(content);
            while (itemM.find()) items.add(itemM.group(1));
            return items;
        }
        return List.of();
    }
}
