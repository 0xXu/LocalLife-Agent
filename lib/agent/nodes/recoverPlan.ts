import { PlanStatuses, type PlannerState } from '../state';

export function recoverPlan(state: PlannerState, reason: string): PlannerState {
  if (reason !== 'restaurant_unavailable' || !state.plan_response) {
    return {
      ...state,
      status: PlanStatuses.EXECUTION_FAILED,
      error: `Unsupported recovery reason: ${reason}`,
    };
  }

  return {
    ...state,
    status: PlanStatuses.RECOVERY,
  };
}
