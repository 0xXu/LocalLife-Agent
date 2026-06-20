package com.meituan.route.data;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;
import reactor.util.retry.Retry;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Supplier;

/**
 * Reliability wrapper for external API calls.
 * Inspired by WePlan's ToolHarness pattern:
 *   timeout → retry with exponential backoff → cache → fallback data.
 *
 * Usage:
 * <pre>
 *   var result = harness.execute(
 *       () -> amapApi.search("restaurant"),
 *       "poi_restaurant_beijing",
 *       fallbackPOIs
 *   );
 * </pre>
 */
public class ToolHarness {

    private static final Logger log = LoggerFactory.getLogger(ToolHarness.class);
    private static final Duration DEFAULT_TIMEOUT = Duration.ofSeconds(8);
    private static final int DEFAULT_MAX_RETRIES = 2;
    private static final Duration INITIAL_BACKOFF = Duration.ofMillis(500);

    // Simple in-memory cache (TTL not implemented — cache lives for JVM lifetime)
    private final Map<String, Object> cache = new ConcurrentHashMap<>();
    private final Duration timeout;
    private final int maxRetries;

    public ToolHarness() {
        this(DEFAULT_TIMEOUT, DEFAULT_MAX_RETRIES);
    }

    public ToolHarness(Duration timeout, int maxRetries) {
        this.timeout = timeout;
        this.maxRetries = maxRetries;
    }

    /**
     * Execute an async call with timeout, retry, and optional caching.
     * On failure, returns the fallback value.
     */
    @SuppressWarnings("unchecked")
    public <T> Mono<T> execute(Supplier<Mono<T>> call, String cacheKey, T fallback) {
        // Check cache first
        if (cacheKey != null && cache.containsKey(cacheKey)) {
            log.debug("[ToolHarness] Cache hit: {}", cacheKey);
            return Mono.just((T) cache.get(cacheKey));
        }

        return call.get()
                .timeout(timeout)
                .retryWhen(Retry.backoff(maxRetries, INITIAL_BACKOFF)
                        .maxBackoff(Duration.ofSeconds(4))
                        .doBeforeRetry(signal -> log.warn("[ToolHarness] Retry {} for {}: {}",
                                signal.totalRetries() + 1, cacheKey, signal.failure().getMessage())))
                .doOnNext(result -> {
                    if (cacheKey != null && result != null) {
                        log.debug("[ToolHarness] Cached: {}", cacheKey);
                        cache.put(cacheKey, result);
                    }
                })
                .onErrorResume(e -> {
                    log.warn("[ToolHarness] All retries exhausted for {}, using fallback. Error: {}",
                            cacheKey, e.getMessage());
                    return fallback != null ? Mono.just(fallback) : Mono.empty();
                })
                .subscribeOn(Schedulers.boundedElastic());
    }

    /**
     * Execute with no fallback (returns empty on failure).
     */
    public <T> Mono<T> execute(Supplier<Mono<T>> call, String cacheKey) {
        return execute(call, cacheKey, null);
    }

    /** Clear a specific cache entry. */
    public void invalidate(String cacheKey) {
        cache.remove(cacheKey);
    }

    /** Clear all cached data. */
    public void clearCache() {
        cache.clear();
        log.info("[ToolHarness] Cache cleared");
    }
}
