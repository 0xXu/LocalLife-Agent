import { ClarificationRequiredPayloadSchema, type ClarificationQuestion, type RunEventEnvelope, type RunStatus } from './schemas';

export type RunState = {
  runId: string | null;
  planId: string | null;
  status: RunStatus | 'idle';
  events: RunEventEnvelope[];
  pendingActions: Array<Record<string, unknown>>;
  currentQuestion: ClarificationQuestion | null;
  error: unknown | null;
};

export const initialRunState: RunState = {
  runId: null,
  planId: null,
  status: 'idle',
  events: [],
  pendingActions: [],
  currentQuestion: null,
  error: null,
};

export function runReducer(state: RunState, event: RunEventEnvelope): RunState {
  if (state.events.some((existing) => isSameEvent(existing, event))) {
    return state;
  }

  const nextState = {
    ...state,
    runId: event.run_id,
    planId: event.plan_id ?? state.planId,
    events: [...state.events, event],
  };

  switch (event.type) {
    case 'run.started':
      return { ...nextState, status: readStatus(event.payload.status, 'running'), currentQuestion: null, error: null };
    case 'run.running':
      return { ...nextState, status: 'running', currentQuestion: null, error: null };
    case 'agent.started':
      return { ...nextState, currentQuestion: null };
    case 'clarification.required':
      return {
        ...nextState,
        status: 'needs_clarification',
        currentQuestion: ClarificationRequiredPayloadSchema.parse(event.payload).question,
      };
    case 'approval.required':
      return {
        ...nextState,
        status: 'approval_required',
        pendingActions: readActions(event.payload.actions),
        currentQuestion: null,
      };
    case 'run.executing':
    case 'actions.execution.started':
      return { ...nextState, status: 'executing', pendingActions: [] };
    case 'actions.execution.completed':
      return { ...nextState, status: 'running' };
    case 'run.completed':
      return { ...nextState, status: readStatus(event.payload.status, 'completed'), pendingActions: [], currentQuestion: null };
    case 'run.failed':
      return {
        ...nextState,
        status: 'failed',
        pendingActions: [],
        currentQuestion: null,
        error: event.payload.error ?? event.payload,
      };
    case 'run.rejected':
      return { ...nextState, status: 'rejected', pendingActions: [], currentQuestion: null };
    case 'guardrail.triggered':
      return { ...nextState, status: 'validation_failed', pendingActions: [], currentQuestion: null, error: event.payload };
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

function isSameEvent(left: RunEventEnvelope, right: RunEventEnvelope) {
  return left.run_id === right.run_id && left.seq === right.seq && left.type === right.type;
}
