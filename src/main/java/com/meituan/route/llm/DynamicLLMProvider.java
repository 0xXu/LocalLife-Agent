package com.meituan.route.llm;

import com.meituan.route.config.ModelProviders;
import com.meituan.route.config.ModelProviders.Provider;
import com.meituan.route.security.ApiKeyEncryptor;
import dev.langchain4j.model.anthropic.AnthropicChatModel;
import dev.langchain4j.model.chat.ChatLanguageModel;
import dev.langchain4j.model.openai.OpenAiChatModel;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Provides per-user ChatLanguageModel instances keyed by (providerId, apiKey).
 *
 * Supports multiple LLM protocols:
 *   - OpenAI-compatible: DeepSeek, OpenAI, Moonshot, Zhipu, Qwen (via OpenAiChatModel)
 *   - Anthropic-native: Claude (via AnthropicChatModel — separate protocol)
 *
 * Falls back to system default (DeepSeek) when no user key is available.
 * User API keys are decrypted via ApiKeyEncryptor before use.
 */
@Component
public class DynamicLLMProvider {

    private static final Logger log = LoggerFactory.getLogger(DynamicLLMProvider.class);

    private final ChatLanguageModel defaultModel;
    private final String defaultProviderId;
    private final Map<String, ChatLanguageModel> cache = new ConcurrentHashMap<>();
    private final ApiKeyEncryptor encryptor;

    public DynamicLLMProvider(ChatLanguageModel defaultModel, ApiKeyEncryptor encryptor) {
        this.defaultModel = defaultModel;
        this.defaultProviderId = "deepseek";
        this.encryptor = encryptor;
    }

    /**
     * Get model for a specific user. Uses their provider + API key.
     * Falls back to system default if no key configured.
     * API key is decrypted at point of use (encrypted at rest in DB).
     */
    public ChatLanguageModel getModel(String providerId, String userApiKey) {
        if (userApiKey == null || userApiKey.isBlank()) {
            return defaultModel;
        }
        final Provider p = ModelProviders.byId(providerId != null ? providerId : "deepseek");
        final Provider resolved = p != null ? p : ModelProviders.byId("deepseek");

        // Decrypt API key at point of use (never plaintext in memory for long)
        String decryptedKey = encryptor.decrypt(userApiKey);

        String cacheKey = resolved.id() + ":" + decryptedKey;
        return cache.computeIfAbsent(cacheKey, k -> {
            log.info("Creating LLM model: provider={}, model={}", resolved.name(), resolved.defaultModel());

            // Anthropic uses a completely different protocol from OpenAI.
            // LangChain4j provides separate model classes for each protocol.
            if ("anthropic".equals(resolved.id())) {
                return AnthropicChatModel.builder()
                        .apiKey(decryptedKey)
                        .modelName(resolved.defaultModel())
                        .timeout(Duration.ofSeconds(30))
                        .maxRetries(1)
                        .logRequests(false)
                        .logResponses(false)
                        .build();
            }

            // All other providers (DeepSeek, OpenAI, Moonshot, Zhipu, Qwen)
            // use the OpenAI-compatible protocol.
            return OpenAiChatModel.builder()
                    .apiKey(decryptedKey)
                    .baseUrl(resolved.baseUrl())
                    .modelName(resolved.defaultModel())
                    .timeout(Duration.ofSeconds(30))
                    .maxRetries(1)
                    .logRequests(false)
                    .logResponses(false)
                    .build();
        });
    }

    public ChatLanguageModel getDefaultModel() {
        return defaultModel;
    }

    public String getDefaultProviderId() {
        return defaultProviderId;
    }
}

