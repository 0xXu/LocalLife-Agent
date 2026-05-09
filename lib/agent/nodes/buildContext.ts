import { type PlannerState } from '../state';

export function buildContext(state: PlannerState): PlannerState {
  return {
    ...state,
    context: {
      city: 'Sendai',
      weather: 'clear',
      data_source: 'seed_verified',
      execution_mode: 'confirmation_required',
    },
  };
}
