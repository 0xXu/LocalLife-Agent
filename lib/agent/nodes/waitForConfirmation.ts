import { PlanStatuses, type PlannerState } from '../state';

export function waitForConfirmation(state: PlannerState): PlannerState {
  return {
    ...state,
    status: PlanStatuses.USER_CONFIRMATION,
    confirmed: false,
    receipts: [],
    pending_side_effects: state.plan_response?.pending_actions ?? [],
  };
}
