import type { PlanResponse } from '../../types/weekendpilot';
import type { PlanListResponse } from '../../types/api';
import { apiRequest, resolveApiUrl } from '../../lib/api/client';

export const scenarioPrompts = {
  family: '今天下午是空的，想和老婆孩子出去玩几个小时，别离家太远。孩子 5 岁，老婆最近在减脂，帮我安排一下。',
  friends: '今天下午朋友 4 个人出去玩，2 男 2 女，先活动再吃饭，想拍照聊天，预算适中，路线顺一点。',
  date: '下午想和对象约会，安静一点，有氛围，排队少，饭前饭后都顺，别安排太累。',
  rainy: '今天下午可能下雨，帮我找室内活动、舒服的餐厅和轻松路线。',
};

export async function buildPlan(goal: string) {
  return apiRequest<PlanResponse>('/api/plans/build', { method: 'POST', body: { goal } });
}

export async function buildPlanStream(
  goal: string,
  callbacks: {
    onStarted?: () => void | Promise<void>;
    onToken?: (content: string) => void | Promise<void>;
    onProgress: (label: string, detail: string) => void | Promise<void>;
  },
): Promise<PlanResponse> {
  const url = resolveApiUrl(`/api/plans/build/stream?goal=${encodeURIComponent(goal)}`);

  return new Promise<PlanResponse>((resolve, reject) => {
    const queue: Array<() => Promise<void>> = [];
    let processing = false;

    async function processNext() {
      if (processing || queue.length === 0) return;
      processing = true;
      await queue.shift()!();
      processing = false;
      processNext();
    }

    const es = new EventSource(url);

    es.onmessage = (e) => {
      const data = JSON.parse(e.data);

      if (data.type === 'started') {
        if (callbacks.onStarted) {
          queue.push(async () => { await callbacks.onStarted!(); });
          processNext();
        }
      } else if (data.type === 'token') {
        if (callbacks.onToken) {
          queue.push(async () => { await callbacks.onToken!(data.content); });
          processNext();
        }
      } else if (data.type === 'progress') {
        queue.push(async () => {
          await callbacks.onProgress(data.label, data.detail);
        });
        processNext();
      } else if (data.type === 'done') {
        es.close();
        resolve(data.result);
      } else if (data.type === 'error') {
        es.close();
        reject(new Error(data.message));
      }
    };

    es.onerror = () => {
      es.close();
      reject(new Error('SSE connection failed'));
    };
  });
}

export async function getPlan(planId: string) {
  return apiRequest<PlanResponse>(`/api/plans/${planId}`);
}

export async function listPlans() {
  return apiRequest<PlanListResponse>('/api/plans');
}

export async function patchConstraints(planId: string, body: Record<string, unknown>) {
  return apiRequest<PlanResponse>(`/api/plans/${planId}/constraints`, { method: 'PATCH', body });
}

export async function buildAlternatives(planId: string) {
  return apiRequest<PlanResponse>(`/api/plans/${planId}/alternatives`, { method: 'POST', body: {} });
}

export async function confirmPlan(planId: string) {
  return apiRequest<PlanResponse>(`/api/plans/${planId}/confirm`, { method: 'POST', body: { confirmed: true } });
}

export async function executePlan(planId: string) {
  return apiRequest<PlanResponse>(`/api/plans/${planId}/execute`, { method: 'POST', body: { confirmed: true } });
}

export async function recoverPlan(planId: string, reason: string) {
  return apiRequest<PlanResponse>(`/api/plans/${planId}/recover`, { method: 'POST', body: { reason } });
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
