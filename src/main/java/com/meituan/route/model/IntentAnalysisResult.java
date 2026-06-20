package com.meituan.route.model;

import java.util.List;

/**
 * Result of LLM-based intent analysis with completeness check.
 * Tells the frontend whether the query is ready for route planning
 * or needs follow-up questions.
 */
public record IntentAnalysisResult(
        String stage,
        UserIntent intent,
        List<String> missingFields,
        List<FollowupQuestion> followupQuestions,
        List<Conflict> conflicts,
        String summaryText
) {
    public record FollowupQuestion(String id, String label, List<String> options) {}
    public record Conflict(String id, String label, String hint) {}
}
