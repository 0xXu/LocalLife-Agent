package com.meituan.route.entity;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.persistence.*;
import java.time.Instant;
import java.util.List;
import java.util.Map;

@Entity
@Table(name = "user_profiles")
public class UserProfileEntity {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false, unique = true, length = 50)
    private String userId;

    @Column(nullable = false, length = 100)
    private String name;

    @Column(name = "profile_name", length = 100)
    private String profileName;

    @Column(name = "preferred_city", length = 50)
    private String preferredCity;

    @Column(name = "avg_budget")
    private Double avgBudget;

    @Column(name = "favorite_categories", columnDefinition = "TEXT")
    private String favoriteCategoriesJson;

    @Column(name = "preference_tags", columnDefinition = "TEXT")
    private String preferenceTagsJson;

    @Column(name = "avoid_tags", columnDefinition = "TEXT")
    private String avoidTagsJson;

    @Column(name = "history_actions", columnDefinition = "TEXT")
    private String historyActionsJson;

    @Column(name = "password_hash", length = 255)
    private String passwordHash;

    @Column(name = "provider_name", length = 50)
    private String providerName;

    @Column(name = "deepseek_api_key", length = 255)
    private String deepseekApiKey;

    @Column(name = "created_at")
    private Instant createdAt;

    @PrePersist
    void prePersist() {
        if (createdAt == null) createdAt = Instant.now();
    }

    // ── Getters / Setters ──

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getUserId() { return userId; }
    public void setUserId(String userId) { this.userId = userId; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getProfileName() { return profileName; }
    public void setProfileName(String profileName) { this.profileName = profileName; }

    public String getPreferredCity() { return preferredCity; }
    public void setPreferredCity(String preferredCity) { this.preferredCity = preferredCity; }

    public Double getAvgBudget() { return avgBudget; }
    public void setAvgBudget(Double avgBudget) { this.avgBudget = avgBudget; }

    public String getFavoriteCategoriesJson() { return favoriteCategoriesJson; }
    public void setFavoriteCategoriesJson(String json) { this.favoriteCategoriesJson = json; }

    public String getPreferenceTagsJson() { return preferenceTagsJson; }
    public void setPreferenceTagsJson(String json) { this.preferenceTagsJson = json; }

    public String getAvoidTagsJson() { return avoidTagsJson; }
    public void setAvoidTagsJson(String json) { this.avoidTagsJson = json; }

    public String getHistoryActionsJson() { return historyActionsJson; }
    public void setHistoryActionsJson(String json) { this.historyActionsJson = json; }

    public String getPasswordHash() { return passwordHash; }
    public void setPasswordHash(String hash) { this.passwordHash = hash; }

    public String getProviderName() { return providerName; }
    public void setProviderName(String name) { this.providerName = name; }

    public String getDeepseekApiKey() { return deepseekApiKey; }
    public void setDeepseekApiKey(String key) { this.deepseekApiKey = key; }

    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }

    // ── JSON helpers ──

    public List<String> parseFavoriteCategories() {
        return parseJson(favoriteCategoriesJson, new TypeReference<List<String>>() {});
    }

    public Map<String, Double> parsePreferenceTags() {
        return parseJson(preferenceTagsJson, new TypeReference<Map<String, Double>>() {});
    }

    public Map<String, Double> parseAvoidTags() {
        return parseJson(avoidTagsJson, new TypeReference<Map<String, Double>>() {});
    }

    public List<String> parseHistoryActions() {
        return parseJson(historyActionsJson, new TypeReference<List<String>>() {});
    }

    private <T> T parseJson(String json, TypeReference<T> typeRef) {
        if (json == null || json.isBlank()) return null;
        try {
            return MAPPER.readValue(json, typeRef);
        } catch (JsonProcessingException e) {
            return null;
        }
    }
}
