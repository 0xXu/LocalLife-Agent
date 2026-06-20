package com.meituan.route.security;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Audit logger for LLM API calls.
 *
 * Records every LLM call with: timestamp, user, provider, model, tokens used,
 * latency, and estimated cost. Also tracks cumulative usage for budget alerts.
 *
 * Enterprise compliance: full audit trail for AI API usage and cost attribution.
 */
@Component
public class LLMAuditLogger {

    private static final Logger audit = LoggerFactory.getLogger("LLM_AUDIT");

    private final AtomicLong totalTokens = new AtomicLong(0);
    private final AtomicLong totalCalls = new AtomicLong(0);
    private final AtomicLong totalCostCents = new AtomicLong(0); // in USD cents × 1000 for precision

    // Per-provider cost per 1M tokens (input), in USD
    private static final java.util.Map<String, Double> COST_PER_1M = java.util.Map.of(
            "deepseek", 0.28,
            "openai", 5.0,
            "moonshot", 1.0,
            "zhipu", 0.5,
            "qwen", 0.5,
            "anthropic", 8.0
    );

    /** Record an LLM call. Returns the audit entry for optional logging to DB. */
    public AuditEntry record(String userId, String provider, String model,
                              int inputTokens, int outputTokens, long latencyMs) {
        int total = inputTokens + outputTokens;
        totalTokens.addAndGet(total);
        totalCalls.incrementAndGet();

        double costPerMillion = (double) COST_PER_1M.getOrDefault(provider, 1.0);
        double costUsd = total / 1_000_000.0 * costPerMillion;
        long costCents = Math.round(costUsd * 100_000); // store with 3 decimal precision
        totalCostCents.addAndGet(costCents);

        var entry = new AuditEntry(
                Instant.now(), userId, provider, model,
                inputTokens, outputTokens, latencyMs, costUsd);

        audit.info("LLM_CALL | user={} | provider={} | model={} | input={} | output={} | latency={}ms | cost=${}",
                userId, provider, model, inputTokens, outputTokens, latencyMs,
                String.format("%.4f", costUsd));

        // Alert if total cost exceeds $1 in this session
        double sessionCost = totalCostCents.get() / 100_000.0;
        if (sessionCost > 1.0 && totalCalls.get() % 50 == 1) {
            audit.warn("LLM_COST_ALERT | session_total=${} | calls={} | tokens={}",
                    String.format("%.4f", sessionCost), totalCalls.get(), totalTokens.get());
        }

        return entry;
    }

    /** Estimate tokens for a prompt before calling the LLM. Conservative heuristic. */
    public int estimateTokens(String prompt) {
        if (prompt == null) return 0;
        // ~1 token per 3.5 Chinese characters or 4 English characters
        return Math.max(10, prompt.length() / 3);
    }

    public long totalTokens() { return totalTokens.get(); }
    public long totalCalls() { return totalCalls.get(); }
    public double totalCostUsd() { return totalCostCents.get() / 100_000.0; }

    public record AuditEntry(
            Instant timestamp,
            String userId,
            String provider,
            String model,
            int inputTokens,
            int outputTokens,
            long latencyMs,
            double costUsd
    ) {}
}
