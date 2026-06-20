package com.meituan.route.service;

import com.meituan.route.entity.UserProfileEntity;
import com.meituan.route.repository.UserProfileRepository;
import com.meituan.route.security.ApiKeyEncryptor;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.*;

@Service
public class AuthService {

    private static final Logger log = LoggerFactory.getLogger(AuthService.class);
    private static final long TOKEN_EXPIRY_HOURS = 72;
    private final SecretKey signingKey;
    private final UserProfileRepository userRepo;
    private final ApiKeyEncryptor encryptor;

    public AuthService(UserProfileRepository userRepo, ApiKeyEncryptor encryptor) {
        this.userRepo = userRepo;
        this.encryptor = encryptor;
        // Read signing key from environment variable, fail fast if not set
        var secret = System.getenv("JWT_SECRET");
        if (secret == null || secret.isBlank()) {
            secret = System.getProperty("jwt.secret");
        }
        if (secret == null || secret.isBlank() || secret.length() < 32) {
            log.warn("JWT_SECRET not set or too short — using generated key (NOT suitable for production)");
            secret = "meituan-route-planner-dev-only-key-do-not-use-in-prod!!";
        }
        // Pad or hash to ensure exactly 32+ bytes for HMAC-SHA
        this.signingKey = Keys.hmacShaKeyFor(
                secret.getBytes(StandardCharsets.UTF_8).length >= 32
                        ? secret.getBytes(StandardCharsets.UTF_8)
                        : hashTo32Bytes(secret));
    }

    private static byte[] hashTo32Bytes(String input) {
        try {
            var md = MessageDigest.getInstance("SHA-256");
            return md.digest(input.getBytes(StandardCharsets.UTF_8));
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    /**
     * Register a new user. When personaId matches a seed profile (user_001/002/003),
     * clone that persona's preferences for personalized recommendations.
     */
    public RegisterResult register(String name, String password, String city, String personaId) {
        String userId = "user_" + UUID.randomUUID().toString().substring(0, 8);

        var existing = userRepo.findAllByOrderByName().stream()
                .filter(e -> e.getName().equals(name)).findAny();
        if (existing.isPresent()) {
            return new RegisterResult(null, null, null, "昵称已被使用");
        }

        // Look up persona seed data if provided
        var personaProfile = (personaId != null && !personaId.isBlank())
                ? userRepo.findByUserId(personaId).orElse(null)
                : null;

        var entity = new UserProfileEntity();
        entity.setUserId(userId);
        entity.setName(name);

        if (personaProfile != null) {
            // Clone persona preferences
            entity.setProfileName(personaProfile.getProfileName() != null
                    ? personaProfile.getProfileName()
                    : (city.equals("上海") ? "上海探索者" : "北京探索者"));
            entity.setPreferredCity(personaProfile.getPreferredCity() != null
                    ? personaProfile.getPreferredCity() : city);
            entity.setAvgBudget(personaProfile.getAvgBudget() > 0
                    ? personaProfile.getAvgBudget() : 150.0);
            entity.setFavoriteCategoriesJson(personaProfile.getFavoriteCategoriesJson());
            entity.setPreferenceTagsJson(personaProfile.getPreferenceTagsJson());
            entity.setAvoidTagsJson(personaProfile.getAvoidTagsJson());
            entity.setHistoryActionsJson("[]");
            entity.setProviderName(personaProfile.getProviderName());
            // Encrypt API key at rest (AES-256-GCM) — decrypted at point of use
            String rawKey = personaProfile.getDeepseekApiKey();
            entity.setDeepseekApiKey(rawKey != null ? encryptor.encrypt(rawKey) : null);
        } else {
            entity.setProfileName(city.equals("上海") ? "上海探索者" : "北京探索者");
            entity.setPreferredCity(city);
            entity.setAvgBudget(150.0);
            entity.setProviderName(null);
            entity.setDeepseekApiKey(null);
            try {
                entity.setFavoriteCategoriesJson("[]");
                entity.setPreferenceTagsJson("{\"高评分\":0.5,\"性价比\":0.5}");
                entity.setAvoidTagsJson("{}");
                entity.setHistoryActionsJson("[]");
            } catch (Exception ignored) {}
        }

        entity.setPasswordHash(hashPassword(password));
        userRepo.save(entity);

        String token = generateToken(userId, name);
        return new RegisterResult(userId, name, token, null);
    }

    /** Login with name + password. */
    public RegisterResult login(String name, String password) {
        var user = userRepo.findAllByOrderByName().stream()
                .filter(e -> e.getName().equals(name) && e.getPasswordHash() != null)
                .findAny();

        if (user.isEmpty()) {
            return new RegisterResult(null, null, null, "用户不存在或未设置密码");
        }
        if (!verifyPassword(password, user.get().getPasswordHash())) {
            return new RegisterResult(null, null, null, "密码错误");
        }

        String token = generateToken(user.get().getUserId(), user.get().getName());
        return new RegisterResult(user.get().getUserId(), user.get().getName(), token, null);
    }

    /** Validate JWT and return userId. */
    public Optional<String> validateToken(String token) {
        try {
            Claims claims = Jwts.parser().verifyWith(signingKey).build()
                    .parseSignedClaims(token).getPayload();
            return Optional.of(claims.getSubject());
        } catch (Exception e) {
            return Optional.empty();
        }
    }

    /** Get a user's DeepSeek API key for LLM calls. */
    public String resolveApiKey(String userId) {
        if (userId == null) return null;
        return userRepo.findByUserId(userId)
                .map(UserProfileEntity::getDeepseekApiKey)
                .orElse(null);
    }

    /** Get user info (name, city, profile) from token. */
    public Map<String, String> getUserInfo(String userId) {
        return userRepo.findByUserId(userId).map(e -> {
            Map<String, String> info = new LinkedHashMap<>();
            info.put("userId", e.getUserId());
            info.put("name", e.getName());
            info.put("profileName", e.getProfileName() != null ? e.getProfileName() : "");
            info.put("preferredCity", e.getPreferredCity() != null ? e.getPreferredCity() : "北京");
            info.put("hasApiKey", e.getDeepseekApiKey() != null && !e.getDeepseekApiKey().isBlank() ? "true" : "false");
            return info;
        }).orElse(Map.of());
    }

    private String generateToken(String userId, String name) {
        return Jwts.builder()
                .subject(userId)
                .claim("name", name)
                .issuedAt(new Date())
                .expiration(Date.from(Instant.now().plusSeconds(TOKEN_EXPIRY_HOURS * 3600)))
                .signWith(signingKey)
                .compact();
    }

    private String hashPassword(String password) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(password.getBytes(StandardCharsets.UTF_8));
            return Base64.getEncoder().encodeToString(hash);
        } catch (Exception e) {
            throw new RuntimeException("Hash failed", e);
        }
    }

    private boolean verifyPassword(String password, String hash) {
        return hashPassword(password).equals(hash);
    }

    public record RegisterResult(String userId, String name, String token, String error) {
        public boolean success() { return token != null; }
    }
}
