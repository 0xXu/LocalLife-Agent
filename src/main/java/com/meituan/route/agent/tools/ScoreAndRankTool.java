package com.meituan.route.agent.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.meituan.route.agent.Tool;
import com.meituan.route.agent.ToolRegistry;
import com.meituan.route.model.Route;
import com.meituan.route.model.UserPreference;
import com.meituan.route.service.UserProfileService;
import com.meituan.route.solver.PreferenceScorer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.*;

@Component
public class ScoreAndRankTool implements Tool {

    private static final Logger log = LoggerFactory.getLogger(ScoreAndRankTool.class);
    private static final ObjectMapper mapper = new ObjectMapper();
    private final PreferenceScorer scorer;
    private final UserProfileService profileService;

    public ScoreAndRankTool(PreferenceScorer scorer, UserProfileService profileService, ToolRegistry registry) {
        this.scorer = scorer;
        this.profileService = profileService;
        registry.register(this);
    }

    @Override public String name() { return "score_and_rank"; }

    @Override
    public String description() {
        return "根据用户偏好画像对路线方案进行打分和排序。返回每条路线的偏好匹配分、匹配标签、UGC评价摘要等。";
    }

    @Override
    public String parametersJson() {
        return """
            {
              "type": "object",
              "properties": {
                "userId": {"type": "string", "description": "用户ID"}
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

            // Return the user profile scoring summary
            var data = Map.<String, Object>of(
                    "userId", profile.userId(),
                    "preferenceTags", profile.preferenceTags() != null ? profile.preferenceTags() : Map.of(),
                    "avoidTags", profile.avoidTags() != null ? profile.avoidTags() : Map.of(),
                    "favoriteCategories", profile.favoriteCategories() != null ? profile.favoriteCategories() : List.of(),
                    "avgBudget", profile.avgBudget());

            var summary = String.format("已就绪偏好打分引擎：偏好维度=%d，避讳维度=%d",
                    profile.preferenceTags().size(), profile.avoidTags().size());
            log.info("ScoreAndRankTool: {}", summary);

            return ToolResult.of(name(), data, summary);
        } catch (Exception e) {
            log.error("ScoreAndRankTool failed", e);
            return ToolResult.of(name(), Map.of(), "打分失败: " + e.getMessage());
        }
    }
}
