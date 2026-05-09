import { PlanStatuses, type PlannerState } from '../state';
import { isRecoveryReason } from '../../recovery/recoveryPolicies';

export function recoverPlan(state: PlannerState, reason: string): PlannerState {
  if (!isRecoveryReason(reason) || !state.plan_response) {
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
