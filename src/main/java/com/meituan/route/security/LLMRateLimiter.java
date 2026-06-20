package com.meituan.route.security;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Token-bucket rate limiter for LLM API calls.
 *
 * Limits per-user and per-IP LLM call rates to prevent:
 *   - API cost explosion from runaway loops
 *   - Denial-of-wallet attacks
 *   - Abuse from a single user/IP
 *
 * Enterprise compliance: predictable cost control for LLM APIs.
 */
@Component
public class LLMRateLimiter {

    private static final Logger log = LoggerFactory.getLogger(LLMRateLimiter.class);

    // Per-user: max calls per minute
    private static final int USER_RPM = 30;
    // Per-IP: max calls per minute
    private static final int IP_RPM = 60;
    // Global: max concurrent LLM calls
    private static final int MAX_CONCURRENT = 10;

    private final Map<String, Bucket> userBuckets = new ConcurrentHashMap<>();
    private final Map<String, Bucket> ipBuckets = new ConcurrentHashMap<>();
    private final AtomicInteger activeCalls = new AtomicInteger(0);

    /** Check and acquire a permit. Returns false if rate-limited. */
    public boolean tryAcquire(String userId, String ipAddress) {
        if (activeCalls.incrementAndGet() > MAX_CONCURRENT) {
            activeCalls.decrementAndGet();
            log.warn("RateLimit: global concurrency limit reached ({} > {})", activeCalls.get(), MAX_CONCURRENT);
            return false;
        }
        if (!checkBucket(userBuckets, userId, USER_RPM)) {
            activeCalls.decrementAndGet();
            log.warn("RateLimit: user {} exceeded {} RPM", userId, USER_RPM);
            return false;
        }
        if (!checkBucket(ipBuckets, ipAddress, IP_RPM)) {
            activeCalls.decrementAndGet();
            log.warn("RateLimit: IP {} exceeded {} RPM", ipAddress, IP_RPM);
            return false;
        }
        return true;
    }

    /** Release a permit when the call completes. */
    public void release() {
        activeCalls.decrementAndGet();
    }

    public int activeCount() { return activeCalls.get(); }

    private boolean checkBucket(Map<String, Bucket> buckets, String key, int rpm) {
        var now = Instant.now();
        var bucket = buckets.computeIfAbsent(key, k -> new Bucket(now, new AtomicInteger(0)));
        synchronized (bucket) {
            if (now.isAfter(bucket.windowStart.plusSeconds(60))) {
                bucket.windowStart = now;
                bucket.count.set(0);
            }
            return bucket.count.incrementAndGet() <= rpm;
        }
    }

    private static class Bucket {
        Instant windowStart;
        AtomicInteger count;
        Bucket(Instant start, AtomicInteger c) { this.windowStart = start; this.count = c; }
    }
}
