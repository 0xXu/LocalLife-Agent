import type { RunEventEnvelope, RunStatus } from './schemas';

export type RunState = {
  runId: string | null;
  planId: string | null;
  status: RunStatus | 'idle';
  events: RunEventEnvelope[];
  pendingActions: Array<Record<string, unknown>>;
  error: unknown | null;
};

export const initialRunState: RunState = {
  runId: null,
  planId: null,
  status: 'idle',
  events: [],
  pendingActions: [],
  error: null,
};

export function runReducer(state: RunState, event: RunEventEnvelope): RunState {
  const nextState = {
    ...state,
    runId: event.run_id,
    planId: event.plan_id ?? state.planId,
    events: [...state.events, event],
  };

  switch (event.type) {
    case 'run.started':
      return { ...nextState, status: readStatus(event.payload.status, 'running'), error: null };
    case 'approval.required':
      return { ...nextState, status: 'approval_required', pendingActions: readActions(event.payload.actions) };
    case 'actions.execution.started':
      return { ...nextState, status: 'executing', pendingActions: [] };
    case 'actions.execution.completed':
      return { ...nextState, status: 'running' };
    case 'run.completed':
      return { ...nextState, status: 'completed', pendingActions: [] };
    case 'run.failed':
      return { ...nextState, status: 'failed', pendingActions: [], error: event.payload.error ?? event.payload };
    case 'run.rejected':
      return { ...nextState, status: 'rejected', pendingActions: [] };
    case 'guardrail.triggered':
      return { ...nextState, status: 'validation_failed', pendingActions: [], error: event.payload };
    default:
      return nextState;
  }
}

function readStatus(value: unknown, fallback: RunStatus): RunStatus {
  return typeof value === 'string' ? (value as RunStatus) : fallback;
}

function readActions(value: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((action): action is Record<string, unknown> => typeof action === 'object' && action !== null);
}
