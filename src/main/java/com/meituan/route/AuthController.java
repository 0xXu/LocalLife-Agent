package com.meituan.route;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.meituan.route.service.AuthService;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import java.util.Map;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    /** POST /api/auth/register — Create account with name, password, city, optional personaId for seed profile cloning. */
    @PostMapping(value = "/register", produces = MediaType.APPLICATION_JSON_VALUE)
    public Mono<Map<String, Object>> register(@RequestBody RegisterRequest req) {
        var result = authService.register(req.name(), req.password(), req.city(), req.personaId());
        if (!result.success()) {
            return Mono.just(Map.of("success", false, "error", result.error()));
        }
        return Mono.just(Map.of(
                "success", true,
                "userId", result.userId(),
                "name", result.name(),
                "token", result.token()
        ));
    }

    /** POST /api/auth/login — Login with name + password. */
    @PostMapping(value = "/login", produces = MediaType.APPLICATION_JSON_VALUE)
    public Mono<Map<String, Object>> login(@RequestBody LoginRequest req) {
        var result = authService.login(req.name(), req.password());
        if (!result.success()) {
            return Mono.just(Map.of("success", false, "error", result.error()));
        }
        return Mono.just(Map.of(
                "success", true,
                "userId", result.userId(),
                "name", result.name(),
                "token", result.token()
        ));
    }

    /** GET /api/auth/me — Get current user info from token. */
    @GetMapping(value = "/me", produces = MediaType.APPLICATION_JSON_VALUE)
    public Mono<Map<String, Object>> me(@RequestHeader(value = "Authorization", required = false) String auth) {
        if (auth == null || !auth.startsWith("Bearer ")) {
            return Mono.just(Map.of("success", false, "error", "未登录"));
        }
        var userId = authService.validateToken(auth.substring(7));
        if (userId.isEmpty()) {
            return Mono.just(Map.of("success", false, "error", "Token 无效或已过期"));
        }
        var info = authService.getUserInfo(userId.get());
        info.put("success", "true");
        @SuppressWarnings("unchecked")
        Map<String, Object> result = (Map<String, Object>) (Map<?, ?>) info;
        return Mono.just(result);
    }

    /** GET /api/auth/models — List available LLM model providers. */
    @GetMapping(value = "/models", produces = MediaType.APPLICATION_JSON_VALUE)
    public Mono<java.util.List<Map<String, String>>> listModels() {
        var list = com.meituan.route.config.ModelProviders.ALL.stream()
                .map(p -> Map.of("id", p.id(), "name", p.name(), "region", p.region(), "apiKeyUrl", p.apiKeyUrl()))
                .toList();
        return Mono.just(list);
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record RegisterRequest(String name, String password, String city, String personaId) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record LoginRequest(String name, String password) {}
}
