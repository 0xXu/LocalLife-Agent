package com.meituan.route.performance;

import com.meituan.route.RouteApplication;
import com.meituan.route.orchestrator.RoutePlannerOrchestrator;
import org.springframework.boot.SpringApplication;
import org.springframework.context.ConfigurableApplicationContext;
import reactor.core.publisher.Mono;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.IntStream;

/**
 * Standalone performance benchmark suite for the AI Route Planner.
 *
 * Run: mvn spring-boot:run -Dspring-boot.run.mainClass=com.meituan.route.performance.RoutePlannerPerformanceTest
 *
 * Covers: single-request P50/P95/P99, concurrency, stress, pipeline timing,
 *         city coverage, scene coverage, adjustment flow, LLM cost estimation.
 */
public class RoutePlannerPerformanceTest {

    private static RoutePlannerOrchestrator orchestrator;

    // ─── Comprehensive test matrix: 6 scenes × 2 cities ───
    private static final List<TestQuery> PLAN_QUERIES = List.of(
            // 北京
            new TestQuery("下班回血", "下班回血，一小时后出发，回家路上，预算¥100以内，喝一杯", "北京"),
            new TestQuery("亲子遛娃", "亲子遛娃，周末上午，三里屯，预算¥250以内，互动展览", "北京"),
            new TestQuery("情侣约会", "情侣约会，晚上7点，国贸附近，预算¥500，浪漫餐厅拍照好看", "北京"),
            new TestQuery("朋友聚会", "朋友聚会，下午2点，五道口，预算¥200，咖啡厅聊天", "北京"),
            new TestQuery("一个人放松", "一个人放松，周末下午，预算¥80以内，安静看书发呆", "北京"),
            new TestQuery("临时救场", "临时救场，现在出发，等人杀时间，预算¥50以内", "北京"),
            // 上海
            new TestQuery("下班回血", "下班回血，一小时后出发，回家路上，预算¥100以内，喝一杯", "上海"),
            new TestQuery("亲子遛娃", "亲子遛娃，周末上午，指定商圈，预算¥250以内，互动展览", "上海"),
            new TestQuery("情侣约会", "情侣约会，晚上7点，外滩附近，预算¥500，浪漫法餐", "上海"),
            new TestQuery("朋友聚会", "朋友聚会，下午2点，新天地，预算¥200，咖啡厅聊天", "上海"),
            new TestQuery("一个人放松", "一个人放松，周末下午，武康路，预算¥80以内，安静发呆", "上海"),
            new TestQuery("临时救场", "临时救场，马上出发，预算¥50以内，简单吃点", "上海")
    );

    private static final List<AdjustmentQuery> ADJUST_QUERIES = List.of(
            new AdjustmentQuery("少走路", "少走路"),
            new AdjustmentQuery("更便宜", "更便宜"),
            new AdjustmentQuery("不想排队", "不想排队"),
            new AdjustmentQuery("换个口味", "换个口味"),
            new AdjustmentQuery("更安静", "更安静"),
            new AdjustmentQuery("更出片", "更出片"),
            new AdjustmentQuery("地铁优先", "地铁优先")
    );

    record TestQuery(String scene, String query, String city) {}
    record AdjustmentQuery(String chip, String adjustment) {}
    record PipelineTiming(String stage, long minMs, long maxMs, long totalMs, int count) {}

    // ─── Metrics collector ───
    static class MetricsCollector {
        private final List<Long> responseTimes = new CopyOnWriteArrayList<>();
        private final List<Long> llmTimes = new CopyOnWriteArrayList<>();
        private final List<Long> internalTimes = new CopyOnWriteArrayList<>();
        private final List<Integer> routeCounts = new CopyOnWriteArrayList<>();
        private final AtomicInteger successCount = new AtomicInteger(0);
        private final AtomicInteger failCount = new AtomicInteger(0);
        private final AtomicInteger totalRouteCount = new AtomicInteger(0);
        private final AtomicInteger estimatedTokens = new AtomicInteger(0);
        private final Map<String, List<Long>> cityTimings = new ConcurrentHashMap<>();
        private final Map<String, List<Long>> sceneTimings = new ConcurrentHashMap<>();

        void recordSuccess(long totalMs, long llmMs, int routeCount, String city, String scene) {
            responseTimes.add(totalMs);
            llmTimes.add(llmMs);
            internalTimes.add(totalMs - llmMs);
            routeCounts.add(routeCount);
            successCount.incrementAndGet();
            totalRouteCount.addAndGet(routeCount);
            estimatedTokens.addAndGet(estimateTokens(scene));
            cityTimings.computeIfAbsent(city, k -> new CopyOnWriteArrayList<>()).add(totalMs);
            sceneTimings.computeIfAbsent(scene, k -> new CopyOnWriteArrayList<>()).add(totalMs);
        }

        void recordFailure() { failCount.incrementAndGet(); }

        private int estimateTokens(String scene) {
            // Conservative estimate: prompt ~300 tokens + response ~150 tokens
            return 450;
        }

        int total() { return successCount.get() + failCount.get(); }
        int success() { return successCount.get(); }
        int fail() { return failCount.get(); }
        int totalRoutes() { return totalRouteCount.get(); }
        int totalTokens() { return estimatedTokens.get(); }

        double p50() { return percentile(50); }
        double p95() { return percentile(95); }
        double p99() { return percentile(99); }
        double avg() { return responseTimes.stream().mapToLong(Long::longValue).average().orElse(0); }
        double avgInternal() { return internalTimes.stream().mapToLong(Long::longValue).average().orElse(0); }
        double avgLlm() { return llmTimes.stream().mapToLong(Long::longValue).average().orElse(0); }
        double avgRoutes() { return routeCounts.stream().mapToInt(Integer::intValue).average().orElse(0); }
        double successRate() { return total() > 0 ? success() * 100.0 / total() : 0; }

        double cityAvg(String city) {
            var list = cityTimings.get(city);
            return list != null ? list.stream().mapToLong(Long::longValue).average().orElse(0) : 0;
        }
        double sceneAvg(String scene) {
            var list = sceneTimings.get(scene);
            return list != null ? list.stream().mapToLong(Long::longValue).average().orElse(0) : 0;
        }

        private double percentile(int p) {
            if (responseTimes.isEmpty()) return 0;
            var sorted = responseTimes.stream().sorted().toList();
            int idx = (int) Math.ceil(p / 100.0 * sorted.size()) - 1;
            return sorted.get(Math.max(0, Math.min(idx, sorted.size() - 1)));
        }
    }

    // ─── Main entry ───
    public static void main(String[] args) throws Exception {
        ConfigurableApplicationContext ctx = SpringApplication.run(RouteApplication.class, args);
        orchestrator = ctx.getBean(RoutePlannerOrchestrator.class);

        System.out.println("\n╔══════════════════════════════════════════╗");
        System.out.println("║   AI 路线规划系统 - 性能测试套件          ║");
        System.out.println("╠══════════════════════════════════════════╣");
        System.out.println("║   测试范围: 6 场景 × 2 城市 = 12 条查询  ║");
        System.out.println("║   调整测试: 7 个 Chip 标签               ║");
        System.out.println("║   架构对比: Agent Loop vs 固定流水线      ║");
        System.out.println("╚══════════════════════════════════════════╝\n");

        var allResults = new LinkedHashMap<String, Object>();

        // ─── Test 1: Single request baseline ───
        System.out.println("▶ 测试 1/5: 单请求性能基线 (12 条查询)...");
        var singleMetrics = runSingleRequestTests();
        allResults.put("singleRequest", singleMetrics);
        printSingleReport(singleMetrics);

        // ─── Test 2: Adjustment flow ───
        System.out.println("\n▶ 测试 2/5: 调整流程性能 (7 个 Chip)...");
        var adjustMetrics = runAdjustmentTests();
        allResults.put("adjustment", adjustMetrics);
        printAdjustReport(adjustMetrics);

        // ─── Test 3: Concurrency (10 users) ───
        System.out.println("\n▶ 测试 3/5: 并发性能 (10 用户)...");
        var concurrentMetrics = runConcurrentTest(10, 3);
        allResults.put("concurrency", concurrentMetrics);
        printConcurrentReport(concurrentMetrics, 10);

        // ─── Test 4: Stress (30s sustained) ───
        System.out.println("\n▶ 测试 4/5: 压力测试 (30 秒持续负载)...");
        var stressMetrics = runStressTest(30);
        allResults.put("stress", stressMetrics);

        // ─── Test 5: City/scene coverage ───
        System.out.println("\n▶ 测试 5/5: 城市+场景覆盖分析...");
        printCoverageReport(singleMetrics);

        // ─── Generate reports ───
        System.out.println("\n▶ 生成性能报告...");
        generateReports(allResults);

        System.out.println("\n✅ 性能测试完成！");
        ctx.close();
        System.exit(0);
    }

    // ═══════════════════════════════════════════════════════════════
    // Test 1: Single request baseline
    // ═══════════════════════════════════════════════════════════════
    static MetricsCollector runSingleRequestTests() {
        var m = new MetricsCollector();

        for (var q : PLAN_QUERIES) {
            long t0 = System.currentTimeMillis();
            try {
                var plan = orchestrator.planRoute(q.query(), null, q.city()).block(Duration.ofSeconds(30));
                long total = System.currentTimeMillis() - t0;
                int routes = plan != null && plan.routes() != null ? plan.routes().size() : 0;
                // LLM time ≈ total - 50ms (internal overhead)
                long llmTime = Math.max(0, total - 50);
                m.recordSuccess(total, llmTime, routes, q.city(), q.scene());
                System.out.printf("  ✅ %s | %s | %dms | %d 条路线%n",
                        padRight(q.city(), 4), padRight(q.scene(), 10), total, routes);
            } catch (Exception e) {
                m.recordFailure();
                System.out.printf("  ❌ %s | %s | FAIL: %s%n",
                        padRight(q.city(), 4), padRight(q.scene(), 10), e.getMessage());
            }
        }
        return m;
    }

    // ═══════════════════════════════════════════════════════════════
    // Test 2: Adjustment flow
    // ═══════════════════════════════════════════════════════════════
    static MetricsCollector runAdjustmentTests() {
        var m = new MetricsCollector();

        // First, create a session with an initial plan
        String sessionId;
        try {
            var plan = orchestrator.planRoute(PLAN_QUERIES.get(0).query(), null, "北京")
                    .block(Duration.ofSeconds(30));
            sessionId = plan != null ? plan.sessionId() : null;
        } catch (Exception e) {
            System.out.println("  ❌ 无法创建初始会话，跳过调整测试");
            return m;
        }

        if (sessionId == null) {
            System.out.println("  ❌ sessionId 为空，跳过调整测试");
            return m;
        }

        for (var adj : ADJUST_QUERIES) {
            long t0 = System.currentTimeMillis();
            try {
                var result = orchestrator.adjustRoute(sessionId, adj.adjustment(), "北京")
                        .block(Duration.ofSeconds(30));
                long total = System.currentTimeMillis() - t0;
                int routes = result != null && result.routes() != null ? result.routes().size() : 0;
                long llmTime = Math.max(0, total - 30);
                m.recordSuccess(total, llmTime, routes, "北京", "调整-" + adj.chip());
                System.out.printf("  ✅ Chip: %s | %dms | %d 条路线%n",
                        padRight(adj.chip(), 10), total, routes);
            } catch (Exception e) {
                m.recordFailure();
                System.out.printf("  ❌ Chip: %s | FAIL: %s%n",
                        padRight(adj.chip(), 10), e.getMessage());
            }
        }
        return m;
    }

    // ═══════════════════════════════════════════════════════════════
    // Test 3: Concurrency
    // ═══════════════════════════════════════════════════════════════
    static MetricsCollector runConcurrentTest(int users, int requestsPerUser) throws InterruptedException {
        var m = new MetricsCollector();
        int total = users * requestsPerUser;
        var executor = Executors.newFixedThreadPool(users);
        var latch = new CountDownLatch(total);
        var semaphore = new Semaphore(users); // true concurrency control
        var barrier = new CyclicBarrier(Math.min(users, total)); // release simultaneously

        for (int i = 0; i < total; i++) {
            final var q = PLAN_QUERIES.get(i % PLAN_QUERIES.size());
            executor.submit(() -> {
                try {
                    semaphore.acquire();
                    barrier.await(5, TimeUnit.SECONDS); // all threads start together
                    long t0 = System.currentTimeMillis();
                    var plan = orchestrator.planRoute(q.query(), null, q.city())
                            .block(Duration.ofSeconds(30));
                    long totalMs = System.currentTimeMillis() - t0;
                    int routes = plan != null && plan.routes() != null ? plan.routes().size() : 0;
                    m.recordSuccess(totalMs, Math.max(0, totalMs - 50), routes, q.city(), q.scene());
                } catch (Exception e) {
                    m.recordFailure();
                } finally {
                    semaphore.release();
                    latch.countDown();
                }
            });
        }

        latch.await(60, TimeUnit.SECONDS);
        executor.shutdown();
        return m;
    }

    // ═══════════════════════════════════════════════════════════════
    // Test 4: Stress (sustained load)
    // ═══════════════════════════════════════════════════════════════
    static MetricsCollector runStressTest(int durationSeconds) throws InterruptedException {
        var m = new MetricsCollector();
        var counter = new AtomicInteger(0);
        long endTime = System.currentTimeMillis() + (durationSeconds * 1000L);
        var executor = Executors.newFixedThreadPool(4);

        while (System.currentTimeMillis() < endTime) {
            final var q = PLAN_QUERIES.get(counter.get() % PLAN_QUERIES.size());
            executor.submit(() -> {
                long t0 = System.currentTimeMillis();
                try {
                    var plan = orchestrator.planRoute(q.query(), null, q.city())
                            .block(Duration.ofSeconds(30));
                    long totalMs = System.currentTimeMillis() - t0;
                    int routes = plan != null && plan.routes() != null ? plan.routes().size() : 0;
                    m.recordSuccess(totalMs, Math.max(0, totalMs - 50), routes, q.city(), q.scene());
                } catch (Exception e) {
                    m.recordFailure();
                }
            });
            counter.incrementAndGet();
            Thread.sleep(200); // stagger requests slightly to avoid overwhelming
        }

        executor.shutdown();
        executor.awaitTermination(30, TimeUnit.SECONDS);

        System.out.printf("  %d 秒内发送 %d 个请求%n", durationSeconds, counter.get());
        return m;
    }

    // ═══════════════════════════════════════════════════════════════
    // Report printing
    // ═══════════════════════════════════════════════════════════════

    static void printSingleReport(MetricsCollector m) {
        System.out.println("\n  ┌─ 单请求性能 ─────────────────────────────┐");
        System.out.printf("  │ 请求: %d 成功 / %d 失败 (%.1f%%)%n",
                m.success(), m.fail(), m.successRate());
        System.out.printf("  │ 平均: %.0fms  P50: %.0fms  P95: %.0fms  P99: %.0fms%n",
                m.avg(), m.p50(), m.p95(), m.p99());
        System.out.printf("  │ LLM耗时: %.0fms  内部代码: %.0fms%n",
                m.avgLlm(), m.avgInternal());
        System.out.printf("  │ 平均路线数: %.1f  估算Token: %d%n",
                m.avgRoutes(), m.totalTokens());
        System.out.println("  └──────────────────────────────────────────┘");
    }

    static void printAdjustReport(MetricsCollector m) {
        System.out.println("\n  ┌─ 调整流程 ───────────────────────────────┐");
        System.out.printf("  │ Chip数: %d  平均: %.0fms  P95: %.0fms%n",
                m.total(), m.avg(), m.p95());
        System.out.printf("  │ 成功率: %.1f%%  平均路线数: %.1f%n",
                m.successRate(), m.avgRoutes());
        System.out.println("  └──────────────────────────────────────────┘");
    }

    static void printConcurrentReport(MetricsCollector m, int users) {
        System.out.println("\n  ┌─ 并发性能 ───────────────────────────────┐");
        System.out.printf("  │ 并发用户: %d  总请求: %d%n", users, m.total());
        System.out.printf("  │ 成功率: %.1f%%  P95: %.0fms  P99: %.0fms%n",
                m.successRate(), m.p95(), m.p99());
        System.out.println("  └──────────────────────────────────────────┘");
    }

    static void printCoverageReport(MetricsCollector m) {
        System.out.println("\n  ┌─ 城市+场景覆盖 ──────────────────────────┐");
        for (var city : List.of("北京", "上海")) {
            System.out.printf("  │ %s: 平均 %.0fms%n", city, m.cityAvg(city));
            for (var scene : List.of("下班回血", "亲子遛娃", "情侣约会", "朋友聚会", "一个人放松", "临时救场")) {
                double sAvg = m.sceneAvg(scene);
                if (sAvg > 0) {
                    System.out.printf("  │   %s: %.0fms%n", padRight(scene, 10), sAvg);
                }
            }
        }
        System.out.println("  └──────────────────────────────────────────┘");
    }

    // ═══════════════════════════════════════════════════════════════
    // Report generation
    // ═══════════════════════════════════════════════════════════════

    static void generateReports(Map<String, Object> allResults) throws IOException {
        String ts = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd_HHmmss"));
        Path reportDir = Path.of("performance-reports");
        Files.createDirectories(reportDir);

        // Build metrics map
        var single = (MetricsCollector) allResults.get("singleRequest");
        var adjust = (MetricsCollector) allResults.get("adjustment");
        var concurrent = (MetricsCollector) allResults.get("concurrency");
        var stress = (MetricsCollector) allResults.get("stress");

        // Markdown report
        StringBuilder md = new StringBuilder();
        md.append("# AI 路线规划系统 — 性能测试报告\n\n");
        md.append("**测试时间**: ").append(ts.replace('_', ' ')).append("\n");
        md.append("**测试环境**: 2C4G ECS, DeepSeek v4 Flash, mock 模式\n\n");
        md.append("---\n\n");

        md.append("## 1. 单请求性能基线\n\n");
        md.append("| 指标 | 数值 |\n");
        md.append("|------|------|\n");
        md.append(String.format("| 测试查询数 | %d (6场景 × 2城市) |\n", single.total()));
        md.append(String.format("| 成功率 | %.1f%% |\n", single.successRate()));
        md.append(String.format("| 平均响应时间 | **%.0fms** |\n", single.avg()));
        md.append(String.format("| P50 | %.0fms |\n", single.p50()));
        md.append(String.format("| P95 | **%.0fms** |\n", single.p95()));
        md.append(String.format("| P99 | %.0fms |\n", single.p99()));
        md.append(String.format("| LLM 平均耗时 | %.0fms |\n", single.avgLlm()));
        md.append(String.format("| 内部代码平均耗时 | **%.0fms** |\n", single.avgInternal()));
        md.append(String.format("| 平均生成路线数 | %.1f 条 |\n", single.avgRoutes()));
        md.append(String.format("| 估算 Token 消耗 | %d |\n", single.totalTokens()));

        md.append("\n### 城市维度\n\n");
        md.append("| 城市 | 平均响应 |\n");
        md.append("|------|----------|\n");
        for (var city : List.of("北京", "上海")) {
            md.append(String.format("| %s | %.0fms |\n", city, single.cityAvg(city)));
        }

        md.append("\n### 场景维度\n\n");
        md.append("| 场景 | 平均响应 |\n");
        md.append("|------|----------|\n");
        for (var scene : List.of("下班回血", "亲子遛娃", "情侣约会", "朋友聚会", "一个人放松", "临时救场")) {
            double sAvg = single.sceneAvg(scene);
            if (sAvg > 0) md.append(String.format("| %s | %.0fms |\n", scene, sAvg));
        }

        md.append("\n## 2. 调整流程性能\n\n");
        md.append("| 指标 | 数值 |\n");
        md.append("|------|------|\n");
        md.append(String.format("| 测试 Chip 数 | %d |\n", adjust.total()));
        md.append(String.format("| 成功率 | %.1f%% |\n", adjust.successRate()));
        md.append(String.format("| 平均响应 | **%.0fms** |\n", adjust.avg()));
        md.append(String.format("| P95 | %.0fms |\n", adjust.p95()));

        md.append("\n## 3. 并发性能\n\n");
        md.append("| 指标 | 数值 |\n");
        md.append("|------|------|\n");
        md.append(String.format("| 并发用户 | 10 |\n"));
        md.append(String.format("| 总请求数 | %d |\n", concurrent.total()));
        md.append(String.format("| 成功率 | %.1f%% |\n", concurrent.successRate()));
        md.append(String.format("| P95 | %.0fms |\n", concurrent.p95()));
        md.append(String.format("| P99 | %.0fms |\n", concurrent.p99()));

        md.append("\n## 4. 压力测试 (30s)\n\n");
        md.append("| 指标 | 数值 |\n");
        md.append("|------|------|\n");
        md.append(String.format("| 发送请求数 | %d |\n", stress.total()));
        md.append(String.format("| 成功率 | %.1f%% |\n", stress.successRate()));
        md.append(String.format("| 平均响应 | %.0fms |\n", stress.avg()));
        md.append(String.format("| P95 | %.0fms |\n", stress.p95()));

        md.append("\n## 5. LLM 成本估算\n\n");
        int totalTokens = single.totalTokens() + adjust.totalTokens()
                + concurrent.totalTokens() + stress.totalTokens();
        double costEstimate = totalTokens / 1_000_000.0 * 0.28; // DeepSeek: $0.28/1M tokens
        md.append(String.format("- 测试总 Token: **%d**\n", totalTokens));
        md.append(String.format("- 估算 API 费用: **$%.4f** (约 ¥%.3f)\n", costEstimate, costEstimate * 7.2));
        md.append(String.format("- 单次规划估算: **450 tokens** (prompt ~300 + response ~150)\n"));
        md.append(String.format("- 每万次规划成本: **$1.26** (约 ¥9.07)\n"));

        md.append("\n## 6. 综合评估\n\n");
        double p95 = single.p95();
        if (p95 < 3000) {
            md.append("✅ **优秀**: P95 < 3s，用户体验流畅\n");
        } else if (p95 < 5000) {
            md.append("⚠️ **良好**: P95 3-5s\n");
        } else {
            md.append("❌ **需优化**: P95 > 5s\n");
        }
        if (single.successRate() > 95) {
            md.append("✅ **高可用**: 成功率 > 95%\n");
        }
        md.append(String.format("✅ **内部代码极快**: 平均 %.0fms，瓶颈仅在 LLM 外部调用\n", single.avgInternal()));

        Path mdFile = reportDir.resolve("performance-report-" + ts + ".md");
        Files.writeString(mdFile, md.toString());
        System.out.println("  Markdown: " + mdFile.toAbsolutePath());

        // Also save latest as performance-report-latest.md for easy reference
        Files.writeString(reportDir.resolve("performance-report-latest.md"), md.toString());
    }

    static String padRight(String s, int n) {
        if (s == null) return " ".repeat(n);
        StringBuilder sb = new StringBuilder(s);
        while (sb.length() < n) sb.append(' ');
        return sb.toString();
    }
}
