import type { PlanResponse } from '../../types/weekendpilot';

export type PlannerState = {
  goal: string;
  result: PlanResponse | null;
  loading: boolean;
  error: string | null;
};

export type PlannerAction =
  | { type: 'request_started'; goal?: string }
  | { type: 'plan_loaded'; result: PlanResponse }
  | { type: 'request_failed'; error: string };

export function plannerReducer(state: PlannerState, action: PlannerAction): PlannerState {
  switch (action.type) {
    case 'request_started':
      return { ...state, goal: action.goal ?? state.goal, loading: true, error: null };
    case 'plan_loaded':
      return { ...state, result: action.result, loading: false, error: null };
    case 'request_failed':
      return { ...state, loading: false, error: action.error };
    default:
      return state;
  }
}
