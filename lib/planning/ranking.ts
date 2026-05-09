import type { ParsedConstraints, PlanVariant } from '../../types/weekendpilot';

export type RankFactors = {
  distance_score: number;
  rating_score: number;
  constraint_fit_score: number;
  availability_score: number;
  route_efficiency_score: number;
  budget_score: number;
  novelty_or_vibe_score: number;
};

export type RankedCandidate = Record<string, unknown> & {
  id: string;
  name?: string;
  title?: string;
  category: string;
  score: number;
  avg_price?: number;
  tags?: string[];
  reason?: string;
  factors?: RankFactors;
};

export type RankedCandidateSet = {
  activities: RankedCandidate[];
  restaurants: RankedCandidate[];
  walks: RankedCandidate[];
};

const weights: Record<keyof RankFactors, number> = {
  distance_score: 0.22,
  rating_score: 0.18,
  constraint_fit_score: 0.16,
  availability_score: 0.14,
  route_efficiency_score: 0.12,
  budget_score: 0.10,
  novelty_or_vibe_score: 0.08,
};

export function scorePoi(factors: RankFactors): number {
  const raw = Object.entries(weights).reduce((total, [key, weight]) => total + weight * factors[key as keyof RankFactors], 0);
  return Math.max(0, Math.min(100, Math.round(raw * 100)));
}

export function factorsForCandidate(candidate: Record<string, unknown>, constraints: ParsedConstraints): RankFactors {
  const distanceKm = Number(candidate.distance_km ?? 5);
  const rating = Number(candidate.rating ?? 4);
  const waitMinutes = Number(candidate.wait_minutes ?? constraints.constraints.max_wait_minutes);
  const avgPrice = Number(candidate.avg_price ?? 2500);
  const tags = Array.isArray(candidate.tags) ? candidate.tags.map(String) : [];

  return {
    distance_score: clamp(1 - distanceKm / Math.max(constraints.constraints.radius_km * 1.4, 1)),
    rating_score: clamp(rating / 5),
    constraint_fit_score: constraintFit(tags, constraints),
    availability_score: clamp(1 - waitMinutes / Math.max(constraints.constraints.max_wait_minutes * 2, 1)),
    route_efficiency_score: clamp(1 - distanceKm / Math.max(constraints.constraints.radius_km * 1.8, 1)),
    budget_score: budgetScore(avgPrice, constraints.preferences.budget_level),
    novelty_or_vibe_score: vibeScore(tags, constraints.scenario),
  };
}

export function rankCandidate(candidate: Record<string, unknown>, constraints: ParsedConstraints): RankedCandidate {
  const factors = factorsForCandidate(candidate, constraints);
  return {
    ...candidate,
    id: String(candidate.id),
    category: String(candidate.category),
    score: scorePoi(factors),
    factors,
  };
}

export function buildVariants(candidates: RankedCandidateSet, constraints: ParsedConstraints): Array<PlanVariant & { estimated_budget: number }> {
  const main = makeVariant('main', '主方案', '综合评分最高的半日路线。', [
    pick(candidates.activities, 'score'),
    pick(candidates.restaurants, 'score'),
    pick(candidates.walks, 'score'),
  ]);
  const budget = makeVariant('budget', '预算优先', '优先选择人均花费更低的组合。', [
    pick(candidates.activities, 'budget'),
    pick(candidates.restaurants, 'budget'),
    pick(candidates.walks, 'budget'),
  ]);
  const comfort = makeVariant('comfort', '舒适优先', '优先选择少等待、少绕路和安静标签。', [
    pick(candidates.activities, 'comfort'),
    pick(candidates.restaurants, 'comfort'),
    pick(candidates.walks, 'comfort'),
  ]);
  const childFirst = makeVariant('child_first', '儿童优先', '优先选择儿童友好标签和较低疲劳度。', [
    pick(candidates.activities, 'child_first'),
    pick(candidates.restaurants, 'child_first'),
    pick(candidates.walks, 'child_first'),
  ]);

  return [main, budget, comfort, childFirst].map((variant) => ({
    ...variant,
    constraint_fit: {
      distance: constraints.constraints.radius_km <= 5 ? 0.94 : 0.9,
      child_friendly: constraints.people.children.length > 0 ? 0.96 : 0.86,
      diet: constraints.preferences.diet.length > 0 ? 0.9 : 0.82,
      time: 0.92,
      budget: variant.kind === 'budget' ? 0.96 : 0.86,
    },
  }));
}

function makeVariant(kind: string, title: string, summary: string, selected: RankedCandidate[]) {
  const itinerary = selected.filter(Boolean).map((candidate, index) => ({
    id: `${kind}_${index + 1}`,
    place_id: candidate.id,
    start: ['14:00', '15:50', '17:10'][index] ?? '18:00',
    end: ['15:30', '16:50', '17:45'][index] ?? '18:30',
    type: candidate.category,
    title: candidate.title ?? candidate.name ?? candidate.id,
    reason: candidate.reason ?? '符合当前约束和排序因子。',
    risk: Array.isArray(candidate.risk_tags) ? candidate.risk_tags.map(String) : [],
  }));
  const estimatedBudget = selected.reduce((total, candidate) => total + Number(candidate.avg_price ?? 0), 0);
  const score = selected.length > 0 ? Math.round(selected.reduce((total, candidate) => total + candidate.score, 0) / selected.length) : 0;

  return {
    id: `variant_${kind}`,
    kind,
    title,
    summary,
    itinerary,
    estimated_budget: estimatedBudget,
    overview: {
      theme: title,
      totalDuration: '4.5 小时',
      driveTime: '约 25 分钟',
      walkingDistance: '1.2 公里',
      estimatedCost: `约 ${estimatedBudget} 円`,
      score,
      estimated_budget_value: estimatedBudget,
    },
    actions: [],
  };
}

function pick(candidates: RankedCandidate[], mode: 'score' | 'budget' | 'comfort' | 'child_first') {
  const sorted = [...candidates].sort((left, right) => {
    if (mode === 'budget') {
      return Number(left.avg_price ?? 0) - Number(right.avg_price ?? 0) || right.score - left.score;
    }
    if (mode === 'comfort') {
      return comfortScore(right) - comfortScore(left) || right.score - left.score;
    }
    if (mode === 'child_first') {
      return childScore(right) - childScore(left) || right.score - left.score;
    }
    return right.score - left.score;
  });
  return sorted[0];
}

function constraintFit(tags: string[], constraints: ParsedConstraints) {
  const requested = [...constraints.preferences.activity, ...constraints.preferences.diet];
  if (requested.length === 0) {
    return 0.8;
  }
  const matched = requested.filter((tag) => tags.includes(tag)).length;
  return clamp(0.65 + matched / requested.length * 0.35);
}

function budgetScore(avgPrice: number, budgetLevel: string) {
  const ceiling = budgetLevel === 'low' ? 1800 : budgetLevel === 'high' ? 6000 : 3600;
  return clamp(1 - avgPrice / (ceiling * 1.5));
}

function vibeScore(tags: string[], scenario: string) {
  const scenarioTags: Record<string, string[]> = {
    family: ['child_friendly', 'educational', 'hands_on'],
    friends: ['chat', 'photo_spot', 'social'],
    date: ['quiet', 'romantic', 'seasonal'],
    rainy_indoor: ['indoor', 'rainy_indoor'],
  };
  return tags.some((tag) => scenarioTags[scenario]?.includes(tag)) ? 0.92 : 0.74;
}

function comfortScore(candidate: RankedCandidate) {
  const factors = candidate.factors;
  const quiet = candidate.tags?.includes('quiet') ? 0.08 : 0;
  return (factors?.availability_score ?? 0.7) + (factors?.route_efficiency_score ?? 0.7) + quiet;
}

function childScore(candidate: RankedCandidate) {
  return (candidate.tags?.includes('child_friendly') ? 1 : 0) + candidate.score / 100;
}

function clamp(value: number) {
  return Math.max(0, Math.min(1, value));
}
