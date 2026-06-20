package com.meituan.route.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;

import java.time.Instant;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Simple in-memory token-bucket rate limiter per client IP.
 * Limits: 30 req/s general API, 10 req/s for auth endpoints.
 * Burst capacity: 2× the rate (allows short spikes).
 * <p>
 * Defense-in-depth: nginx also rate-limits, this covers direct-to-backend access.
 */
@Component
@Order(2)
public class RateLimitFilter implements WebFilter {

    private static final Logger log = LoggerFactory.getLogger(RateLimitFilter.class);

    // General API: 30 tokens/s, burst 60
    private static final double GENERAL_RATE = 30.0;
    private static final double GENERAL_BURST = 60.0;

    // Auth endpoints: 10 tokens/s, burst 20 (credential stuffing protection)
    private static final double AUTH_RATE = 10.0;
    private static final double AUTH_BURST = 20.0;

    // Bucket cleanup: remove entries older than 5 minutes
    private static final long CLEANUP_INTERVAL_MS = 300_000;

    private final ConcurrentHashMap<String, TokenBucket> buckets = new ConcurrentHashMap<>();
    private volatile long lastCleanup = System.currentTimeMillis();

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        String path = exchange.getRequest().getPath().value();

        // Only rate-limit API paths
        if (!path.startsWith("/api/")) {
            return chain.filter(exchange);
        }

        String clientIp = getClientIp(exchange);
        boolean isAuthPath = path.startsWith("/api/auth/");
        double rate = isAuthPath ? AUTH_RATE : GENERAL_RATE;
        double burst = isAuthPath ? AUTH_BURST : GENERAL_BURST;

        // Periodic cleanup of stale buckets
        long now = System.currentTimeMillis();
        if (now - lastCleanup > CLEANUP_INTERVAL_MS) {
            lastCleanup = now;
            buckets.entrySet().removeIf(e ->
                    Instant.now().toEpochMilli() - e.getValue().lastRefill > CLEANUP_INTERVAL_MS);
        }

        TokenBucket bucket = buckets.computeIfAbsent(clientIp,
                k -> new TokenBucket(burst, rate, Instant.now()));

        if (!bucket.tryConsume()) {
            log.warn("Rate limit exceeded for IP {} on path {}", clientIp, path);
            exchange.getResponse().setStatusCode(HttpStatus.TOO_MANY_REQUESTS);
            exchange.getResponse().getHeaders().add("Retry-After", "1");
            return exchange.getResponse().setComplete();
        }

        return chain.filter(exchange);
    }

    private String getClientIp(ServerWebExchange exchange) {
        // Check X-Forwarded-For (set by nginx) first
        String forwarded = exchange.getRequest().getHeaders().getFirst("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank()) {
            // Take the first IP in the chain (original client)
            int comma = forwarded.indexOf(',');
            return comma > 0 ? forwarded.substring(0, comma).trim() : forwarded.trim();
        }
        // Fall back to remote address
        var remote = exchange.getRequest().getRemoteAddress();
        return remote != null ? remote.getAddress().getHostAddress() : "unknown";
    }

    /**
     * Simple token bucket implementation.
     */
    private static class TokenBucket {
        final double burstCapacity;
        final double refillRate; // tokens per second
        double tokens;
        volatile long lastRefill;

        TokenBucket(double initialTokens, double refillRate, Instant now) {
            this.burstCapacity = initialTokens;
            this.refillRate = refillRate;
            this.tokens = initialTokens;
            this.lastRefill = now.toEpochMilli();
        }

        synchronized boolean tryConsume() {
            refill();
            if (tokens >= 1.0) {
                tokens -= 1.0;
                return true;
            }
            return false;
        }

        private void refill() {
            long now = Instant.now().toEpochMilli();
            double elapsed = (now - lastRefill) / 1000.0;
            if (elapsed > 0) {
                tokens = Math.min(burstCapacity, tokens + elapsed * refillRate);
                lastRefill = now;
            }
        }
    }
}
