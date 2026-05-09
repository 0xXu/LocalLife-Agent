import type { ParsedConstraints, PlanResponse, Receipt } from '../../types/weekendpilot';

export const PlanStatuses = {
  INPUT: 'INPUT',
  PARSE_CONSTRAINTS: 'PARSE_CONSTRAINTS',
  NEED_CLARIFICATION: 'NEED_CLARIFICATION',
  SEARCH_CANDIDATES: 'SEARCH_CANDIDATES',
  RANK_AND_FILTER: 'RANK_AND_FILTER',
  BUILD_ITINERARY: 'BUILD_ITINERARY',
  VALIDATE_PLAN: 'VALIDATE_PLAN',
  USER_CONFIRMATION: 'USER_CONFIRMATION',
  EXECUTE_ACTIONS: 'EXECUTE_ACTIONS',
  EXECUTION_FAILED: 'EXECUTION_FAILED',
  RECOVERY: 'RECOVERY',
  SEND_SUMMARY: 'SEND_SUMMARY',
  DONE: 'DONE',
} as const;

export type PlanWorkflowStatus = (typeof PlanStatuses)[keyof typeof PlanStatuses];

export type CandidateSet = {
  activities: Array<Record<string, unknown>>;
  restaurants: Array<Record<string, unknown>>;
  walks: Array<Record<string, unknown>>;
};

export type PlannerState = {
  thread_id: string;
  status: PlanWorkflowStatus;
  goal?: string;
  confirmed?: boolean;
  clarifying_questions: string[];
  constraints?: ParsedConstraints & Record<string, unknown>;
  context?: Record<string, unknown>;
  candidates?: CandidateSet;
  ranked_candidates?: CandidateSet;
  plan_response?: PlanResponse;
  receipts: Receipt[];
  pending_side_effects: Array<Record<string, unknown>>;
  openai_metadata?: {
    llm_fallback: boolean;
    agent?: string;
  };
  error?: string;
};

export type PlannerInput = {
  goal?: string;
  confirmed?: boolean;
  plan_response?: PlanResponse;
};

export type PlannerRunnableConfig = {
  configurable?: {
    thread_id?: string;
  };
};

export type PlannerCheckpointer = {
  get(threadId: string): PlannerState | undefined | Promise<PlannerState | undefined>;
  put(threadId: string, state: PlannerState): void | Promise<void>;
};

export const sideEffectTools = new Set([
  'reserve_activity',
  'create_reservation',
  'claim_coupon',
  'create_order',
  'send_plan_message',
  'create_calendar_event',
]);

export function createInitialState(threadId: string, input: PlannerInput): PlannerState {
  return {
    thread_id: threadId,
    status: PlanStatuses.INPUT,
    goal: input.goal,
    confirmed: input.confirmed,
    clarifying_questions: [],
    receipts: [],
    pending_side_effects: [],
    plan_response: input.plan_response,
  };
}
