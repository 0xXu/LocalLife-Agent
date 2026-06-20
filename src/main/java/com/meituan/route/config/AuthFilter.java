package com.meituan.route.config;

import com.meituan.route.service.AuthService;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;

import java.util.List;

/**
 * Protects /api/route/** endpoints — requires valid JWT token.
 * /api/auth/** and /api/route/health are public.
 */
@Component
@Order(1)
public class AuthFilter implements WebFilter {

    private static final List<String> PUBLIC_PATHS = List.of(
            "/api/auth/", "/api/route/health", "/api/route/profiles", "/api/route/pois"
    );

    private final AuthService authService;

    public AuthFilter(AuthService authService) {
        this.authService = authService;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        String path = exchange.getRequest().getPath().value();

        // Allow public paths
        for (var publicPath : PUBLIC_PATHS) {
            if (path.startsWith(publicPath)) {
                return chain.filter(exchange);
            }
        }

        // Allow OPTIONS (CORS preflight)
        if ("OPTIONS".equalsIgnoreCase(exchange.getRequest().getMethod().name())) {
            return chain.filter(exchange);
        }

        // Only protect /api/route/ endpoints
        if (!path.startsWith("/api/route/") && !path.startsWith("/api/favorites")) {
            return chain.filter(exchange);
        }

        String auth = exchange.getRequest().getHeaders().getFirst("Authorization");
        if (auth == null || !auth.startsWith("Bearer ")) {
            exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
            return exchange.getResponse().setComplete();
        }

        var userId = authService.validateToken(auth.substring(7));
        if (userId.isEmpty()) {
            exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
            return exchange.getResponse().setComplete();
        }

        // Attach userId to request attributes for downstream use
        exchange.getAttributes().put("userId", userId.get());
        return chain.filter(exchange);
    }
}
