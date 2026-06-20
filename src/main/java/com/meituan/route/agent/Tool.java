package com.meituan.route.agent;

import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

import java.util.Map;

/**
 * Tool interface for the Agent Loop architecture.
 * Each tool wraps an existing agent or service, exposing it as a
 * callable function that the LLM-driven main Agent can invoke dynamically.
 *
 * The LLM receives tool descriptions and decides which tool to call next,
 * replacing the fixed 5-agent pipeline with flexible, on-demand execution.
 */
public interface Tool {

    /** Unique tool name, e.g. "search_pois". Used in LLM function-call JSON. */
    String name();

    /** Human-readable description. Shown to the LLM as the tool's purpose. */
    String description();

    /**
     * JSON Schema describing this tool's parameters.
     * Follows OpenAI/Anthropic function-calling format.
     */
    String parametersJson();

    /**
     * Execute the tool synchronously with the given JSON arguments string.
     * The implementation parses arguments, delegates to the wrapped agent/service,
     * and returns a structured result.
     */
    ToolResult execute(String arguments);

    /**
     * Execute the tool asynchronously (reactive).
     * Default implementation wraps the synchronous call on boundedElastic scheduler.
     */
    default Mono<ToolResult> executeAsync(String arguments) {
        return Mono.fromCallable(() -> execute(arguments))
                .subscribeOn(Schedulers.boundedElastic());
    }

    /**
     * Result returned by every tool execution.
     * @param toolName  the tool that produced this result
     * @param data      structured output data (routes, POIs, scores, etc.)
     * @param summary   human-readable summary for the LLM's next decision step
     */
    record ToolResult(String toolName, Map<String, Object> data, String summary) {
        public static ToolResult of(String toolName, Map<String, Object> data, String summary) {
            return new ToolResult(toolName, data, summary);
        }
    }
}
