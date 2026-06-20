package com.meituan.route.agent.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.meituan.route.agent.Tool;
import com.meituan.route.agent.ToolRegistry;
import com.meituan.route.model.UserPreference;
import com.meituan.route.service.UserProfileService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.Map;

@Component
public class GetUserProfileTool implements Tool {

    private static final Logger log = LoggerFactory.getLogger(GetUserProfileTool.class);
    private static final ObjectMapper mapper = new ObjectMapper();

    private final UserProfileService profileService;

    public GetUserProfileTool(UserProfileService profileService, ToolRegistry registry) {
        this.profileService = profileService;
        registry.register(this);
    }

    @Override public String name() { return "get_user_profile"; }

    @Override
    public String description() {
        return "获取用户的历史偏好画像，包含偏好标签、避讳标签、常选分类、历史行为等。用于个性化路线推荐。";
    }

    @Override
    public String parametersJson() {
        return """
            {
              "type": "object",
              "properties": {
                "userId": {"type": "string", "description": "用户ID，如 user_001"}
              },
              "required": ["userId"]
            }""";
    }

    @Override
    public ToolResult execute(String arguments) {
        try {
            var node = mapper.readTree(arguments);
            var userId = node.has("userId") ? node.get("userId").asText() : "";
            var profile = profileService.getUserProfile(userId).block();
            if (profile == null) profile = UserPreference.neutral();

            var data = Map.<String, Object>of(
                    "userId", profile.userId() != null ? profile.userId() : userId,
                    "name", profile.name() != null ? profile.name() : "",
                    "profileName", profile.profileName() != null ? profile.profileName() : "",
                    "preferredCity", profile.preferredCity() != null ? profile.preferredCity() : "",
                    "avgBudget", profile.avgBudget(),
                    "favoriteCategories", profile.favoriteCategories() != null ? profile.favoriteCategories() : java.util.List.of(),
                    "preferenceTags", profile.preferenceTags() != null ? profile.preferenceTags() : Map.of(),
                    "avoidTags", profile.avoidTags() != null ? profile.avoidTags() : Map.of()
            );

            var summary = String.format("用户%s（%s）：偏好=%s，避讳=%s",
                    profile.name(), profile.profileName(),
                    profile.preferenceTags().keySet(), profile.avoidTags().keySet());

            log.info("GetUserProfileTool: {}", summary);
            return ToolResult.of(name(), data, summary);
        } catch (Exception e) {
            log.error("GetUserProfileTool failed", e);
            return ToolResult.of(name(), Map.of(), "获取用户画像失败: " + e.getMessage());
        }
    }
}
