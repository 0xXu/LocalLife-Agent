package com.meituan.route.agent;

import org.springframework.stereotype.Component;

import java.util.*;
import java.util.stream.Collectors;

/**
 * Registry of all available Tools for the Agent Loop.
 * The LLM receives the full tool list and decides which to call.
 */
@Component
public class ToolRegistry {

    private final Map<String, Tool> tools = new LinkedHashMap<>();

    /** Register a tool. Called automatically by Spring via constructor injection. */
    public void register(Tool tool) {
        tools.put(tool.name(), tool);
    }

    /** Get a tool by name. */
    public Optional<Tool> get(String name) {
        return Optional.ofNullable(tools.get(name));
    }

    /** List all registered tools. */
    public List<Tool> listAll() {
        return List.copyOf(tools.values());
    }

    /**
     * Build the tools description block for the LLM system prompt.
     * Format follows Anthropic/OpenAI function-calling conventions.
     */
    public String buildToolsPrompt() {
        var sb = new StringBuilder();
        sb.append("你可以调用以下工具来完成路线规划任务：\n\n");
        for (var tool : tools.values()) {
            sb.append("### ").append(tool.name()).append("\n");
            sb.append(tool.description()).append("\n");
            sb.append("参数: ").append(tool.parametersJson()).append("\n\n");
        }
        sb.append("---\n");
        sb.append("调用工具时，请返回JSON格式：\n");
        sb.append("{\"action\": \"call_tool\", \"tool\": \"工具名\", \"arguments\": {...}}\n\n");
        sb.append("当所有必要信息收集完毕后，返回：\n");
        sb.append("{\"action\": \"finish\", \"summary\": \"...\", \"routes\": [...]}\n");
        return sb.toString();
    }

    /**
     * Build a simplified tool list for logging / debugging.
     */
    public String summarize() {
        return tools.values().stream()
                .map(t -> t.name() + ": " + t.description())
                .collect(Collectors.joining("\n"));
    }
}
