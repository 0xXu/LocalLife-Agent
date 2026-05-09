import { PlanStatuses, type PlannerState } from '../state';
import { rankExplanationAgentName } from '../agents';

export type RankFactors = {
  distance_score: number;
  rating_score: number;
  constraint_fit_score: number;
  availability_score: number;
  route_efficiency_score: number;
  budget_score: number;
  novelty_or_vibe_score: number;
};

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
