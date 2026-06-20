package com.meituan.route.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.meituan.route.entity.UserProfileEntity;
import com.meituan.route.model.POI;
import com.meituan.route.model.Route;
import com.meituan.route.model.UserPreference;
import com.meituan.route.repository.UserProfileRepository;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

import java.util.*;
import java.util.stream.Collectors;

@Service
public class UserProfileService {

    private static final Logger log = LoggerFactory.getLogger(UserProfileService.class);
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private final UserProfileRepository repo;

    public UserProfileService(UserProfileRepository repo) {
        this.repo = repo;
    }

    @PostConstruct
    void seedProfiles() {
        // Ensure seed users have passwords (for persona card login)
        ensureSeedPassword("user_001");
        ensureSeedPassword("user_002");
        ensureSeedPassword("user_003");

        if (repo.findByUserId("user_001").isPresent()) {
            log.info("User profiles already seeded, skipping");
            return;
        }
        log.info("Seeding 3 mock user profiles...");
        seed("user_001", "小林", "约会偏好型", "上海", 200.0,
                List.of("日料", "咖啡", "展览", "西餐"),
                Map.of("安静", 0.90, "少排队", 0.85, "拍照好看", 0.80, "适合约会", 0.78, "日料", 0.72, "少走路", 0.60),
                Map.of("排队久", 0.90, "太吵", 0.80, "距离远", 0.70),
                List.of("收藏过安静咖啡馆", "多次选择少走路路线", "经常点击适合约会的餐厅", "跳过排队超过30分钟的餐厅"));
        seed("user_002", "阿航", "效率通勤型", "北京", 120.0,
                List.of("快餐", "商场", "咖啡", "简餐"),
                Map.of("少走路", 0.92, "近地铁", 0.88, "不用排队", 0.82, "省时", 0.80, "性价比", 0.70),
                Map.of("绕路", 0.90, "等位久", 0.85, "距离远", 0.82),
                List.of("多次点击少走路", "收藏近地铁餐厅", "经常选择2小时以内路线"));
        seed("user_003", "Mia", "探店内容型", "上海", 300.0,
                List.of("网红餐厅", "甜品", "买手店", "咖啡"),
                Map.of("出片", 0.95, "新店", 0.88, "热门", 0.82, "高评分", 0.80, "拍照好看", 0.78),
                Map.of("普通", 0.85, "没特色", 0.82, "环境一般", 0.70),
                List.of("收藏过多家网红甜品店", "经常选择拍照出片路线", "分享过探店路线卡片"));
        log.info("Seeded 3 user profiles");
    }

    private void seed(String userId, String name, String profileName, String city, double budget,
                      List<String> favCats, Map<String, Double> prefTags, Map<String, Double> avoidTags,
                      List<String> history) {
        var e = new UserProfileEntity();
        e.setUserId(userId);
        e.setName(name);
        e.setProfileName(profileName);
        e.setPreferredCity(city);
        e.setAvgBudget(budget);
        // Set default password "1234" for seed users so they can login via persona cards
        e.setPasswordHash(hashPassword("1234"));
        try {
            e.setFavoriteCategoriesJson(MAPPER.writeValueAsString(favCats));
            e.setPreferenceTagsJson(MAPPER.writeValueAsString(prefTags));
            e.setAvoidTagsJson(MAPPER.writeValueAsString(avoidTags));
            e.setHistoryActionsJson(MAPPER.writeValueAsString(history));
        } catch (JsonProcessingException ex) {
            log.error("Failed to serialize profile {}", userId, ex);
            return;
        }
        repo.save(e);
    }

    public Mono<UserPreference> getUserProfile(String userId) {
        if (userId == null || userId.isBlank()) return Mono.just(UserPreference.neutral());
        return Mono.fromCallable(() -> repo.findByUserId(userId))
                .subscribeOn(Schedulers.boundedElastic())
                .map(opt -> opt.map(this::toDomain).orElse(UserPreference.neutral()));
    }

    /** Resolve user's LLM provider + API key for dynamic model selection. */
    public record UserApiKey(String providerName, String apiKey) {}
    public Mono<UserApiKey> resolveApiKey(String userId) {
        if (userId == null || userId.isBlank()) return Mono.just(new UserApiKey(null, null));
        return Mono.fromCallable(() -> repo.findByUserId(userId))
                .subscribeOn(Schedulers.boundedElastic())
                .map(opt -> opt.map(e -> {
                    String key = e.getDeepseekApiKey();
                    String provider = e.getProviderName();
                    if (key == null || key.isBlank()) return new UserApiKey(null, null);
                    return new UserApiKey(provider != null ? provider : "deepseek", key);
                }).orElse(new UserApiKey(null, null)));
    }

    public Mono<List<UserPreference>> listAllProfiles() {
        return Mono.fromCallable(() -> repo.findAllByOrderByName().stream().map(this::toDomain).toList())
                .subscribeOn(Schedulers.boundedElastic());
    }

    /**
     * Update user preference profile based on a favorited route.
     * Extracts POI tags and categories from the route, then boosts the
     * corresponding preference tags — so future recommendations are
     * personalized based on the user's actual favorites history.
     */
    public void learnFromFavorite(String userId, Route route) {
        if (userId == null || userId.isBlank() || route == null) return;
        var opt = repo.findByUserId(userId);
        if (opt.isEmpty()) return;

        var entity = opt.get();
        var prefTags = entity.parsePreferenceTags() != null
                ? new LinkedHashMap<String, Double>(entity.parsePreferenceTags()) : new LinkedHashMap<String, Double>();
        var avoidTags = entity.parseAvoidTags() != null
                ? new LinkedHashMap<String, Double>(entity.parseAvoidTags()) : new LinkedHashMap<String, Double>();
        var favCats = entity.parseFavoriteCategories() != null
                ? new ArrayList<String>(entity.parseFavoriteCategories()) : new ArrayList<String>();
        var history = entity.parseHistoryActions() != null
                ? new ArrayList<String>(entity.parseHistoryActions()) : new ArrayList<String>();

        // Boost preference tags from each POI in the route
        for (var seg : route.segments()) {
            POI poi = seg.poi();
            // Tags: boost weight by +0.03 per favorite (capped at 1.0)
            for (var tag : poi.tags()) {
                prefTags.merge(tag, 0.53, (old, delta) -> Math.min(1.0, old + 0.03));
            }
            // Category: add to favorite categories if not already present
            if (poi.category() != null && !favCats.contains(poi.category())) {
                // Use user-friendly names
                var catName = switch (poi.category()) {
                    case "RESTAURANT" -> "美食";
                    case "SHOPPING" -> "购物";
                    case "ATTRACTION" -> "景点";
                    case "ENTERTAINMENT" -> "娱乐";
                    case "CULTURE" -> "文化";
                    default -> poi.category();
                };
                if (!favCats.contains(catName)) {
                    favCats.add(catName);
                }
            }
        }

        // Record action in history
        var routeName = route.name() != null ? route.name() : "路线";
        history.add("收藏了「" + routeName + "」(" + route.segments().size() + "站)");
        // Keep history manageable — only keep last 50 entries
        if (history.size() > 50) {
            history = new ArrayList<String>(history.subList(history.size() - 50, history.size()));
        }

        // Save back
        try {
            entity.setPreferenceTagsJson(MAPPER.writeValueAsString(prefTags));
            entity.setAvoidTagsJson(MAPPER.writeValueAsString(avoidTags));
            entity.setFavoriteCategoriesJson(MAPPER.writeValueAsString(favCats));
            entity.setHistoryActionsJson(MAPPER.writeValueAsString(history));
            repo.save(entity);
            log.info("Updated preference profile for user={}: +{} tags, {} categories, {} history items",
                    userId, route.segments().stream().map(s -> s.poi().tags().size()).reduce(0, Integer::sum),
                    favCats.size(), history.size());
        } catch (JsonProcessingException e) {
            log.warn("Failed to update preference profile: {}", e.getMessage());
        }
    }

    private UserPreference toDomain(UserProfileEntity e) {
        return new UserPreference(
                e.getUserId(), e.getName(), e.getProfileName(), e.getPreferredCity(),
                e.getAvgBudget() != null ? e.getAvgBudget() : 0,
                e.parseFavoriteCategories() != null ? e.parseFavoriteCategories() : List.of(),
                e.parsePreferenceTags() != null ? e.parsePreferenceTags() : Map.of(),
                e.parseAvoidTags() != null ? e.parseAvoidTags() : Map.of(),
                e.parseHistoryActions() != null ? e.parseHistoryActions() : List.of()
        );
    }

    /** Ensure seed users have a password set so persona card login works. */
    private void ensureSeedPassword(String userId) {
        repo.findByUserId(userId).ifPresent(e -> {
            if (e.getPasswordHash() == null || e.getPasswordHash().isBlank()) {
                e.setPasswordHash(hashPassword("1234"));
                repo.save(e);
                log.info("Set default password for seed user {}", userId);
            }
        });
    }

    private static String hashPassword(String password) {
        try {
            var md = java.security.MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(password.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            return java.util.Base64.getEncoder().encodeToString(hash);
        } catch (java.security.NoSuchAlgorithmException e) {
            throw new RuntimeException("Hash failed", e);
        }
    }
}
