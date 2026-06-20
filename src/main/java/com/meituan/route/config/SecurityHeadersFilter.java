package com.meituan.route.config;

import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;

/**
 * Adds security-related HTTP response headers to every response.
 * Defense-in-depth: nginx also sets these, but this covers direct-to-backend access.
 */
@Component
@Order(0)
public class SecurityHeadersFilter implements WebFilter {

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        var headers = exchange.getResponse().getHeaders();

        // Prevent clickjacking
        headers.add("X-Frame-Options", "DENY");
        // Prevent MIME-type sniffing
        headers.add("X-Content-Type-Options", "nosniff");
        // Enable browser XSS filter
        headers.add("X-XSS-Protection", "1; mode=block");
        // Restrict referrer information
        headers.add("Referrer-Policy", "strict-origin-when-cross-origin");
        // Disable cross-domain policies
        headers.add("X-Permitted-Cross-Domain-Policies", "none");
        // Restrict resource loading
        headers.add("Cross-Origin-Resource-Policy", "same-origin");

        return chain.filter(exchange);
    }
}
