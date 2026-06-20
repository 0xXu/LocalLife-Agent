package com.meituan.route.config;

import java.util.List;
import java.util.Map;

/**
 * Available LLM model providers for user registration.
 * Each provider has a display name, base URL, default model name, and a URL
 * where users can obtain their API key.
 */
public final class ModelProviders {

    public record Provider(
            String id,
            String name,
            String baseUrl,
            String defaultModel,
            String apiKeyUrl,
            String region
    ) {}

    public static final List<Provider> ALL = List.of(
            new Provider("deepseek", "DeepSeek", "https://api.deepseek.com/v1",
                    "deepseek-chat", "https://platform.deepseek.com/api_keys", "国内"),
            new Provider("openai", "OpenAI", "https://api.openai.com/v1",
                    "gpt-4o", "https://platform.openai.com/api-keys", "国外"),
            new Provider("moonshot", "Moonshot 月之暗面", "https://api.moonshot.cn/v1",
                    "moonshot-v1-8k", "https://platform.moonshot.cn/console/api-keys", "国内"),
            new Provider("zhipu", "智谱 GLM", "https://open.bigmodel.cn/api/paas/v4",
                    "glm-4-flash", "https://open.bigmodel.cn/usercenter/apikeys", "国内"),
            new Provider("qwen", "通义千问", "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "qwen-plus", "https://dashscope.console.aliyun.com/apiKey", "国内"),
            new Provider("anthropic", "Anthropic Claude", "https://api.anthropic.com/v1",
                    "claude-sonnet-4-20250514", "https://console.anthropic.com/settings/keys", "国外")
    );

    public static Provider byId(String id) {
        return ALL.stream().filter(p -> p.id().equals(id)).findFirst().orElse(null);
    }

    public static final Map<String, String> DEFAULT_KEYS = Map.of(
            "deepseek", System.getenv().getOrDefault("DEEPSEEK_API_KEY", ""),
            "openai", System.getenv().getOrDefault("OPENAI_API_KEY", ""),
            "moonshot", System.getenv().getOrDefault("MOONSHOT_API_KEY", ""),
            "zhipu", System.getenv().getOrDefault("ZHIPU_API_KEY", ""),
            "qwen", System.getenv().getOrDefault("QWEN_API_KEY", ""),
            "anthropic", System.getenv().getOrDefault("ANTHROPIC_API_KEY", "")
    );
}
