package com.meituan.route.agent.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.meituan.route.agent.ConversationAgent;
import com.meituan.route.agent.Tool;
import com.meituan.route.agent.ToolRegistry;
import com.meituan.route.model.UserIntent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.Map;

/**
 * Wraps ConversationAgent as a Tool.
 * Parses natural language into structured UserIntent.
 */
@Component
public class ParseIntentTool implements Tool {

    private static final Logger log = LoggerFactory.getLogger(ParseIntentTool.class);
    private static final ObjectMapper mapper = new ObjectMapper();

    private final ConversationAgent conversationAgent;

    public ParseIntentTool(ConversationAgent conversationAgent, ToolRegistry registry) {
        this.conversationAgent = conversationAgent;
        registry.register(this);
    }

    @Override
    public String name() { return "parse_user_intent"; }

    @Override
    public String description() {
        return "解析用户的自然语言输入，提取城市、区域、预算、时间、偏好、场景等结构化意图。";
    }

    @Override
    public String parametersJson() {
        return """
            {
              "type": "object",
              "properties": {
                "query": {"type": "string", "description": "用户的自然语言输入"},
                "sessionId": {"type": "string", "description": "会话ID（可选）"},
                "cityHint": {"type": "string", "description": "城市提示（可选）"}
              },
              "required": ["query"]
            }""";
    }

    @Override
    public ToolResult execute(String arguments) {
        try {
            var node = mapper.readTree(arguments);
            var query = node.has("query") ? node.get("query").asText() : "";
            var sessionId = node.has("sessionId") ? node.get("sessionId").asText() : null;
            var cityHint = node.has("cityHint") ? node.get("cityHint").asText() : null;

            var result = conversationAgent.processAsync(query, sessionId, cityHint).block();
            if (result == null) return ToolResult.of(name(), Map.of(), "意图解析失败");

            var intent = result.intent();
            var data = Map.<String, Object>of(
                    "sessionId", result.sessionId(),
                    "city", intent.city() != null ? intent.city() : "",
                    "district", intent.district() != null ? intent.district() : "",
                    "budget", intent.budget(),
                    "categories", intent.preferredCategories() != null ? intent.preferredCategories() : java.util.List.of(),
                    "keywords", intent.keywords() != null ? intent.keywords() : java.util.List.of(),
                    "startTime", intent.startTime() != null ? intent.startTime().toString() : "",
                    "endTime", intent.endTime() != null ? intent.endTime().toString() : "",
                    "optimizationGoal", intent.optimizationGoal() != null ? intent.optimizationGoal() : "",
                    "specialRequest", intent.specialRequest() != null ? intent.specialRequest() : ""
            );

            var summary = String.format("已解析用户意图：城市=%s，区域=%s，预算=%.0f，分类=%s",
                    data.get("city"), data.get("district"), intent.budget(),
                    intent.preferredCategories());

            log.info("ParseIntentTool: {}", summary);
            return ToolResult.of(name(), data, summary);
        } catch (Exception e) {
            log.error("ParseIntentTool failed", e);
            return ToolResult.of(name(), Map.of(), "解析失败: " + e.getMessage());
        }
    }
}
