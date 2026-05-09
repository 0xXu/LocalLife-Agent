import { PlanStatuses, type PlannerState } from '../state';
import { rankExplanationAgentName } from '../agents';
import { hardFilterCandidates, type FilterablePoi } from '../../planning/filtering';
import { rankCandidate, type RankFactors } from '../../planning/ranking';

export type { RankFactors };

export type RankedPoiExplanationInput = {
  name: string;
  factors: RankFactors;
  facts: string[];
};

export type RankedPoiExplanation = {
  name: string;
  agent: string;
  top_reasons: string[];
  tradeoffs: string[];
  factors: RankFactors;
};

export function rankCandidates(state: PlannerState): PlannerState {
  const constraints = state.constraints;
  if (!constraints) {
    throw new Error('Cannot rank candidates before constraints are parsed.');
  }

  const filterInput = {
    date: constraints.time_window.date,
    time: constraints.time_window.start,
    radiusKm: constraints.constraints.radius_km,
    childAges: constraints.people.children.map((child) => child.age),
    partySize: constraints.people.adults + constraints.people.children.length,
    maxWaitMinutes: constraints.constraints.max_wait_minutes,
  };
  const activities = hardFilterCandidates(asFilterable(state.candidates?.activities), filterInput);
  const restaurants = hardFilterCandidates(asFilterable(state.candidates?.restaurants), filterInput);
  const walks = hardFilterCandidates(asFilterable(state.candidates?.walks), filterInput);

  return {
    ...state,
    status: PlanStatuses.RANK_AND_FILTER,
    filtered_candidates: {
      activities,
      restaurants,
      walks,
    },
    rejected_candidates: [...activities.rejected, ...restaurants.rejected, ...walks.rejected],
    ranked_candidates: {
      activities: activities.map((candidate) => rankCandidate(candidate, constraints)).sort(byScore),
      restaurants: restaurants.map((candidate) => rankCandidate(candidate, constraints)).sort(byScore),
      walks: walks.map((candidate) => rankCandidate(candidate, constraints)).sort(byScore),
    },
  };
}

function byScore(left: Record<string, unknown>, right: Record<string, unknown>) {
  return Number(right.score ?? 0) - Number(left.score ?? 0);
}

function asFilterable(candidates: Array<Record<string, unknown>> = []) {
  return candidates as Array<Record<string, unknown> & FilterablePoi>;
}

export async function explainRankedPoi(input: RankedPoiExplanationInput): Promise<RankedPoiExplanation> {
  return {
    name: input.name,
    agent: rankExplanationAgentName,
    top_reasons: input.facts.slice(0, 3),
    tradeoffs: buildTradeoffs(input.factors),
    factors: input.factors,
  };
}

function buildTradeoffs(factors: RankFactors) {
  const tradeoffs: string[] = [];

  if (factors.budget_score < 0.9) {
    tradeoffs.push('预算匹配不是最高分，需要确认人均花费是否可接受。');
  }

  if (factors.route_efficiency_score < 0.9) {
    tradeoffs.push('路线效率略低，需要在氛围和少走路之间权衡。');
  }

  if (factors.novelty_or_vibe_score < 0.8) {
    tradeoffs.push('新鲜感或氛围分不高，但基础约束匹配更稳定。');
  }

  return tradeoffs.length > 0 ? tradeoffs : ['各项评分较均衡，主要风险来自实时库存和排队变化。'];
}
