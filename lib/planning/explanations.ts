import type { RejectedCandidate } from './filtering';
import type { RankFactors } from './ranking';

export type GroundedExplanationInput = {
  facts: string[];
  factors: RankFactors;
  rejected?: RejectedCandidate[];
};

export function explainGroundedChoice(input: GroundedExplanationInput) {
  return {
    top_reasons: input.facts.slice(0, 3),
    tradeoffs: tradeoffsFromFactors(input.factors),
    rejected_reasons: input.rejected ?? [],
  };
}

function tradeoffsFromFactors(factors: RankFactors) {
  const tradeoffs: string[] = [];
  if (factors.budget_score < 0.8) {
    tradeoffs.push('预算评分偏低，需要确认总价是否可接受。');
  }
  if (factors.route_efficiency_score < 0.8) {
    tradeoffs.push('路线效率不是最优，需要权衡体验和移动成本。');
  }
  if (factors.availability_score < 0.8) {
    tradeoffs.push('可订性存在波动，需要保留替代方案。');
  }
  return tradeoffs.length > 0 ? tradeoffs : ['评分因子较均衡，主要风险来自实时库存变化。'];
}
