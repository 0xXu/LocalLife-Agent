import type {
  ActionKind,
  GoalEditPayload,
  PlanEditPayload,
  PreferenceFact,
  RealityEventKind,
  TaskSnapshot,
} from './types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8787';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: '请求失败' }));
    throw new Error(payload.detail || '请求失败');
  }
  return response.json() as Promise<T>;
}

export const taskApi = {
  create(goal: string): Promise<TaskSnapshot> {
    return request('/api/tasks', {
      method: 'POST',
      body: JSON.stringify({ goal, user_id: 'demo-user' }),
    });
  },
  get(taskId: string): Promise<TaskSnapshot> {
    return request(`/api/tasks/${taskId}`);
  },
  message(taskId: string, content: string): Promise<TaskSnapshot> {
    return request(`/api/tasks/${taskId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  },
  selectDecision(taskId: string, optionId: string): Promise<TaskSnapshot> {
    return request(`/api/tasks/${taskId}/decisions`, {
      method: 'POST',
      body: JSON.stringify({ option_id: optionId }),
    });
  },
  editGoal(taskId: string, edit: GoalEditPayload): Promise<TaskSnapshot> {
    return request(`/api/tasks/${taskId}/goal`, {
      method: 'PATCH',
      body: JSON.stringify(edit),
    });
  },
  editPlan(taskId: string, edit: PlanEditPayload): Promise<TaskSnapshot> {
    return request(`/api/tasks/${taskId}/plan-edits`, {
      method: 'POST',
      body: JSON.stringify({ keep_other_nodes: true, ...edit }),
    });
  },
  stop(taskId: string): Promise<TaskSnapshot> {
    return request(`/api/tasks/${taskId}/stop`, { method: 'POST' });
  },
  mandate(taskId: string): Promise<TaskSnapshot> {
    return request(`/api/tasks/${taskId}/mandate`, { method: 'POST' });
  },
  transaction(taskId: string): Promise<TaskSnapshot> {
    return request(`/api/tasks/${taskId}/transaction`, { method: 'POST' });
  },
  compensate(taskId: string, fulfillmentEventId: string, action: ActionKind): Promise<TaskSnapshot> {
    return request(`/api/tasks/${taskId}/compensations`, {
      method: 'POST',
      body: JSON.stringify({ fulfillment_event_id: fulfillmentEventId, action }),
    });
  },
  supplyAction(taskId: string, nodeId: string, action: ActionKind): Promise<TaskSnapshot> {
    return request(`/api/tasks/${taskId}/supply-actions`, {
      method: 'POST',
      body: JSON.stringify({ node_id: nodeId, action }),
    });
  },
  realityEvent(
    taskId: string,
    event: { kind: RealityEventKind; detail: string; magnitude?: number; node_id?: string; location?: string; completion_source?: 'user_confirmation' | 'provider_status' | 'redemption' | 'arrival'; provider_status?: string },
  ): Promise<TaskSnapshot> {
    return request(`/api/tasks/${taskId}/reality-events`, {
      method: 'POST',
      body: JSON.stringify(event),
    });
  },
  outcomeCheckIn(
    taskId: string,
    response: 'achieved' | 'partly' | 'not_achieved',
    note?: string,
  ): Promise<TaskSnapshot> {
    return request(`/api/tasks/${taskId}/outcome-check-in`, {
      method: 'POST',
      body: JSON.stringify({ response, note }),
    });
  },
  scenario(scenario: string): Promise<{ world_version: number }> {
    return request(`/api/world/scenarios/${scenario}`, { method: 'POST' });
  },
  preferences(): Promise<PreferenceFact[]> {
    return request('/api/preferences?user_id=demo-user');
  },
  revisePreference(
    factId: string,
    edit: { preference?: string; context_scope?: string; delete?: boolean },
  ): Promise<PreferenceFact> {
    return request(`/api/preferences/${factId}?user_id=demo-user`, {
      method: 'PATCH',
      body: JSON.stringify(edit),
    });
  },
  eventUrl(taskId: string): string {
    return `${API_URL}/api/tasks/${taskId}/events`;
  },
};
