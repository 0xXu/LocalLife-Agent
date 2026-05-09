import { PlanStatuses, type PlannerState } from '../state';

export function rankCandidates(state: PlannerState): PlannerState {
  return {
    ...state,
    status: PlanStatuses.RANK_AND_FILTER,
    ranked_candidates: {
      activities: [...(state.candidates?.activities ?? [])].sort(byScore),
      restaurants: [...(state.candidates?.restaurants ?? [])].sort(byScore),
      walks: [...(state.candidates?.walks ?? [])].sort(byScore),
    },
  };
}

function byScore(left: Record<string, unknown>, right: Record<string, unknown>) {
  return Number(right.score ?? 0) - Number(left.score ?? 0);
}
