import { PlanStatuses, type PlannerState } from '../state';
import { loadSeedPois } from '../../data/repositories/poiRepository';

export async function searchCandidates(state: PlannerState): Promise<PlannerState> {
  const constraints = state.constraints;
  if (!constraints) {
    throw new Error('Cannot search candidates before constraints are parsed.');
  }

  const pois = await loadSeedPois();
  const radiusKm = Number(constraints.constraints.radius_km ?? 5);
  const scenario = constraints.scenario;
  const requestedTags = [...constraints.preferences.activity, ...constraints.preferences.diet];
  const inScope = pois
    .filter((poi) => poi.distance_km <= radiusKm)
    .filter((poi) => poi.supported_scenarios.includes(scenario))
    .map((poi) => ({ ...poi, title: poi.name }));

  return {
    ...state,
    status: PlanStatuses.SEARCH_CANDIDATES,
    candidates: {
      activities: prioritize(inScope.filter((poi) => ['family_activity', 'social_activity', 'date_activity', 'indoor_activity'].includes(poi.category)), requestedTags),
      restaurants: prioritize(inScope.filter((poi) => poi.category === 'restaurant'), constraints.preferences.diet),
      walks: prioritize(inScope.filter((poi) => poi.category === 'dessert_walk' || poi.category === 'citywalk'), requestedTags),
    },
  };
}

function prioritize(candidates: Array<Record<string, unknown> & { tags: string[]; rating: number; distance_km: number }>, tags: string[]) {
  return candidates
    .sort((left, right) => tagScore(right.tags, tags) - tagScore(left.tags, tags) || right.rating - left.rating || left.distance_km - right.distance_km)
    .slice(0, 12);
}

function tagScore(candidateTags: string[], requestedTags: string[]) {
  return requestedTags.filter((tag) => candidateTags.includes(tag)).length;
}
