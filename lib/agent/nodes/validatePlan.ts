import { PlanResponseSchema } from '../../contracts/schemas';
import { PlanStatuses, type PlannerState } from '../state';

export function validatePlan(state: PlannerState): PlannerState {
  if (!state.plan_response) {
    return {
      ...state,
      status: PlanStatuses.EXECUTION_FAILED,
      error: 'Plan response is missing before validation.',
    };
  }

  const plan_response = {
    ...PlanResponseSchema.parse(state.plan_response),
    itinerary: state.plan_response.plan.itinerary,
  };

  return {
    ...state,
    status: PlanStatuses.VALIDATE_PLAN,
    plan_response: plan_response as typeof state.plan_response,
  };
}
