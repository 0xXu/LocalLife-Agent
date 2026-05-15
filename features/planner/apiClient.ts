import type { GraphRunEvent, GraphRunStartResponse, PlanResponse } from '../../types/weekendpilot';
import type { PlanListResponse } from '../../types/api';
import { apiRequest, resolveApiUrl } from '../../lib/api/client';

export const scenarioPrompts = {
  family: '今天下午是空的，想和老婆孩子出去玩几个小时，别离家太远。孩子 5 岁，老婆最近在减脂，帮我安排一下。',
  friends: '今天下午朋友 4 个人出去玩，2 男 2 女，先活动再吃饭，想拍照聊天，预算适中，路线顺一点。',
  date: '下午想和对象约会，安静一点，有氛围，排队少，饭前饭后都顺，别安排太累。',
  rainy: '今天下午可能下雨，帮我找室内活动、舒服的餐厅和轻松路线。',
};

export async function startPlanRun(goal: string, userId = 'local_demo_user') {
  return apiRequest<GraphRunStartResponse>('/api/plans/runs', {
    method: 'POST',
    body: { goal, user_id: userId },
  });
}

export async function getPlan(planId: string) {
  return apiRequest<PlanResponse>(`/api/plans/${planId}`);
}

export async function listPlans() {
  return apiRequest<PlanListResponse>('/api/plans');
}

export function streamRunUpdates(
  runId: string,
  callbacks: {
    onGraphUpdate?: (event: GraphRunEvent) => void | Promise<void>;
    onError?: (error: Error) => void;
  },
) {
  const es = new EventSource(resolveApiUrl(`/api/plans/runs/${runId}/stream`));

  es.addEventListener('graph_update', (event) => {
    void callbacks.onGraphUpdate?.(JSON.parse((event as MessageEvent).data));
    es.close();
  });

  es.onerror = () => {
    if (es.readyState === EventSource.CLOSED) {
      callbacks.onError?.(new Error('SSE connection failed'));
    }
  };

  return () => es.close();
}

export async function resumePlan(planId: string, selectedActionIds: string[]) {
  return apiRequest<PlanResponse>(`/api/plans/${planId}/resume`, {
    method: 'POST',
    body: { decision: 'approve', selected_action_ids: selectedActionIds },
  });
}

export async function rejectPlan(planId: string) {
  return apiRequest<PlanResponse>(`/api/plans/${planId}/resume`, {
    method: 'POST',
    body: { decision: 'reject' },
  });
}

export async function getPlanVersions(planId: string) {
  return apiRequest<{ plan_id: string; versions: Array<Record<string, unknown>> }>(`/api/plans/${planId}/versions`);
}

export async function getTraces(planId: string) {
  return apiRequest<{ planId: string; trace: PlanResponse['trace']; tool_calls: PlanResponse['tool_calls'] }>(`/api/traces/${planId}`);
}

export async function getToolSchemas() {
  return apiRequest<{ tools: Array<Record<string, unknown>> }>('/api/tool-schemas');
}

export async function getHealth() {
  return apiRequest<{ status: string; service: string; mode: string }>('/api/health');
}

// --- User Profile ---

export interface BackendUserPreference {
  key: string;
  value: unknown;
  source: string;
  confidence: number;
  scope: string;
  evidence: string;
  expires_at: string;
  user_editable: boolean;
  sensitive: boolean;
}

export interface BackendUserProfile {
  user_id: string;
  explicit_preferences: BackendUserPreference[];
  learned_preferences: BackendUserPreference[];
  session_preferences: BackendUserPreference[];
}

export async function getUserProfile(userId: string) {
  return apiRequest<BackendUserProfile>(`/api/users/${userId}/profile`);
}

export async function saveUserProfile(userId: string, profile: BackendUserProfile) {
  return apiRequest<BackendUserProfile>(`/api/users/${userId}/profile`, {
    method: 'POST',
    body: profile as unknown as Record<string, unknown>,
  });
}

// --- LLM Status ---

export interface LlmStatus {
  provider: string;
  protocol: string;
  base_url: string;
  model: string;
  api_key: string;
  configured: boolean;
  remote_enabled: boolean;
  response_format: string;
  disable_thinking: boolean;
}

export async function getLlmStatus() {
  return apiRequest<LlmStatus>('/api/llm/status');
}
