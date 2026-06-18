import { apiRequest, resolveApiUrl } from '../../lib/api/client';
import {
  CreateRunResponseSchema,
  RunEventEnvelopeSchema,
  type CreateRunResponse,
  type RunEventEnvelope,
} from './schemas';

export type CreateRunInput = {
  goal: string;
  user_id?: string;
  mode?: 'plan';
};

export type RunEventCallbacks = {
  onEvent?: (event: RunEventEnvelope) => void | Promise<void>;
  onError?: (error: Error) => void;
};

export async function createRun(input: CreateRunInput): Promise<CreateRunResponse> {
  const data = await apiRequest<unknown>('/api/runs', {
    method: 'POST',
    body: input,
  });

  return CreateRunResponseSchema.parse(data);
}

export async function approveRunActions(runId: string, actionIds: string[]) {
  return apiRequest<unknown>(`/api/runs/${runId}/actions/approve`, {
    method: 'POST',
    body: { action_ids: actionIds },
  });
}

export async function rejectRun(runId: string, reason = 'user_rejected') {
  return apiRequest<unknown>(`/api/runs/${runId}/actions/reject`, {
    method: 'POST',
    body: { reason },
  });
}

export function streamRunEvents(runId: string, callbacks: RunEventCallbacks = {}) {
  const es = new EventSource(resolveApiUrl(`/api/runs/${runId}/events`));

  es.onmessage = (message) => {
    const event = RunEventEnvelopeSchema.parse(JSON.parse(message.data));
    void callbacks.onEvent?.(event);
  };

  es.onerror = () => {
    if (es.readyState === EventSource.CLOSED) {
      callbacks.onError?.(new Error('SSE connection failed'));
    }
  };

  return () => {
    es.close();
  };
}
