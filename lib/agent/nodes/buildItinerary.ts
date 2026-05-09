import { v7 as uuidv7 } from 'uuid';

import { PlanResponseSchema } from '../../contracts/schemas';
import type { PlanAction, PlanResponse, Receipt, TraceSpan } from '../../../types/weekendpilot';
import { PlanStatuses, type PlannerState, sideEffectTools } from '../state';
import { buildVariants, type RankedCandidate, type RankedCandidateSet } from '../../planning/ranking';

export function buildItinerary(state: PlannerState): PlannerState {
  const plan_response = makePlanResponse(state);
  return {
    ...state,
    status: PlanStatuses.BUILD_ITINERARY,
    plan_response,
    pending_side_effects: plan_response.pending_actions,
  };
}

export function makePlanResponse(state: Pick<PlannerState, 'constraints' | 'goal' | 'thread_id' | 'ranked_candidates' | 'rejected_candidates'>): PlanResponse {
  const constraints = state.constraints;
  if (!constraints) {
    throw new Error('Cannot build itinerary before constraints are parsed.');
  }

  const ranked = normalizeRankedCandidates(state.ranked_candidates);
  const variants = buildVariants(ranked, constraints);
  const itinerary = variants[0].itinerary;
  const actions = makeActions();
  const averageScore = Math.round([...ranked.activities, ...ranked.restaurants, ...ranked.walks].slice(0, 3).reduce((total, candidate) => total + candidate.score, 0) / 3);
  const estimatedBudget = variants[0].estimated_budget;
  const route = makeRoute(ranked);
  const response = {
    constraints,
    progress: [
      '理解出行需求',
      '筛选亲子活动',
      '匹配健康餐厅',
      '规划顺路路线',
      '确认可订时间',
    ],
    trace: [
      trace('parse_user_goal', '解析出家庭、饮食、距离和半日时长约束。', 'ok'),
      trace('search_local_activities', '找到 5 公里内适合亲子的活动地点。', 'ok'),
      trace('search_restaurants', '匹配附近带低脂菜单标识的餐厅。', 'ok'),
      trace('rank_candidates', `按详细设计权重排序，筛除 ${state.rejected_candidates?.length ?? 0} 个不满足硬约束的候选。`, 'ok', {
        rejected: state.rejected_candidates ?? [],
        top_scores: [
          ranked.activities[0]?.score,
          ranked.restaurants[0]?.score,
          ranked.walks[0]?.score,
        ].filter((score) => score !== undefined),
      }),
      trace('optimize_route', '生成科学馆 -> 轻食餐厅 -> 河畔散步路线。', 'ok'),
      trace('check_availability', '绿荫轻食餐厅 15:55 有 3 人模拟可订席位。', 'ok'),
    ],
    tool_calls: [
      toolCall('parse_user_goal'),
      toolCall('search_local_activities'),
      toolCall('search_restaurants'),
      toolCall('rank_candidates', 'ok', {
        rejected_reasons: state.rejected_candidates ?? [],
        factor_scores: {
          activity: ranked.activities[0]?.factors,
          restaurant: ranked.restaurants[0]?.factors,
          walk: ranked.walks[0]?.factors,
        },
      }),
      toolCall('optimize_route'),
      toolCall('check_availability'),
      toolCall('reserve_activity', 'pending'),
      toolCall('create_reservation', 'pending'),
      toolCall('claim_coupon', 'pending'),
      toolCall('create_order', 'pending'),
      toolCall('send_plan_message', 'pending'),
      toolCall('create_calendar_event', 'pending'),
    ],
    pending_actions: actions.map((action, index) => ({
      id: `pending_${index + 1}`,
      type: action.type,
      tool: action.tool ?? action.type,
      label: action.label ?? action.type,
      requires_confirmation: true,
      payload: action.payload,
    })),
    route,
    itinerary,
    plan: {
      id: `plan_${uuidv7().slice(0, 8)}`,
      status: 'pending_confirmation',
      title: '亲子科学馆 + 健康轻食半日计划',
      summary: '科学馆亲子活动、低脂轻食餐厅、饭后河畔散步和确认后执行回执。',
      constraint_fit: { distance: 0.95, child_friendly: 1, diet: 0.9, time: 0.92, budget: 0.86 },
      itinerary,
      overview: {
        theme: '下午 · 家庭 · 健康轻松',
        totalDuration: '4.5 小时',
        driveTime: '约 25 分钟',
        walkingDistance: '1.2 公里',
        estimatedCost: `约 ${estimatedBudget} 円`,
        score: averageScore,
        estimated_budget_value: estimatedBudget,
      },
      actions,
      variants,
      receipts: [],
      badges: ['5 公里内', '儿童友好', '低脂菜单', '可执行'],
    },
    actions,
    variants,
    receipts: [],
  };

  return {
    ...PlanResponseSchema.parse(response),
    itinerary,
  } as PlanResponse;
}

function makeActions(): Array<PlanAction & Record<string, unknown>> {
  return [
    action('activity_reservation', 'reserve_activity', '预约亲子活动', '城市科学馆', '3 人入场名额，下午 14:00 到 15:40。'),
    action('restaurant_reservation', 'create_reservation', '预订轻食餐厅', '绿荫轻食餐厅', '15:55，3 人桌位，低脂菜单优先。'),
    action('coupon', 'claim_coupon', '领取餐饮优惠券', '绿荫轻食餐厅', '领取低脂套餐 9 折券。'),
    action('order', 'create_order', '预点低糖饮品', '河畔甜品店', '预留下单低糖饮品和儿童点心。'),
    action('message', 'send_plan_message', '发送计划给家人', '家庭群聊', '发送时间轴、路线和预算摘要。'),
    action('calendar', 'create_calendar_event', '写入日历', '家庭日历', '创建 14:00 到 17:40 的半日计划。'),
  ];
}

function action(type: string, toolName: string, label: string, target: string, detail: string): PlanAction & Record<string, unknown> {
  return {
    type,
    tool: toolName,
    label,
    target,
    detail,
    requires_confirmation: true,
    payload: { target, detail },
  };
}

export function makeReceipts(planResponse: PlanResponse): Receipt[] {
  const title = planResponse.plan.itinerary[0]?.title ?? '活动';
  return [
    receipt('activity_reservation', 'reserve_activity', 'TKT-2041', `已为 3 人预约${title}。`),
    receipt('restaurant_reservation', 'create_reservation', 'RES-3812', '已预订绿荫轻食餐厅 15:55 的 3 人桌。'),
    receipt('coupon', 'claim_coupon', 'CPN-1098', '已领取低脂套餐 9 折券。'),
    receipt('order', 'create_order', 'ORD-5527', '已预点低糖饮品和儿童点心。'),
    receipt('message', 'send_plan_message', 'MSG-9128', '计划摘要已发送到家庭群聊。'),
    receipt('calendar', 'create_calendar_event', 'CAL-7743', '家庭日历已创建半日计划。'),
  ];
}

function receipt(type: string, toolName: string, id: string, detail: string): Receipt {
  return {
    type,
    tool: toolName,
    id,
    status: 'confirmed',
    detail,
    payload: {},
  };
}

function normalizeRankedCandidates(candidates: PlannerState['ranked_candidates']): RankedCandidateSet {
  return {
    activities: fallbackRanked(candidates?.activities, fallbackActivity),
    restaurants: fallbackRanked(candidates?.restaurants, fallbackRestaurant),
    walks: fallbackRanked(candidates?.walks, fallbackWalk),
  };
}

function fallbackRanked(candidates: Array<Record<string, unknown>> | undefined, fallback: RankedCandidate): RankedCandidate[] {
  const normalized = (candidates ?? []).map((candidate) => ({
    ...candidate,
    id: String(candidate.id),
    category: String(candidate.category ?? candidate.type ?? 'activity'),
    name: String(candidate.name ?? candidate.title ?? candidate.id),
    title: String(candidate.title ?? candidate.name ?? candidate.id),
    score: Number(candidate.score ?? 75),
    avg_price: Number(candidate.avg_price ?? 1000),
    tags: Array.isArray(candidate.tags) ? candidate.tags.map(String) : [],
  })) as RankedCandidate[];
  return normalized.length > 0 ? normalized : [fallback];
}

const fallbackActivity: RankedCandidate = { id: 'act_001', name: '城市科学馆', title: '城市科学馆', category: 'family_activity', score: 91, avg_price: 1800, tags: ['child_friendly'], reason: '有亲子探索展区，室内路线轻松。' };
const fallbackRestaurant: RankedCandidate = { id: 'res_014', name: '绿荫轻食餐厅', title: '绿荫轻食餐厅', category: 'restaurant', score: 90, avg_price: 3000, tags: ['low_fat'], reason: '有低脂套餐和儿童座椅。' };
const fallbackWalk: RankedCandidate = { id: 'walk_006', name: '河畔低糖甜品散步', title: '河畔低糖甜品散步', category: 'dessert_walk', score: 86, avg_price: 900, tags: ['low_sugar'], reason: '饭后短距离散步，沿路有低糖饮品选择。' };

function makeRoute(ranked: RankedCandidateSet) {
  const selected = [ranked.activities[0], ranked.restaurants[0], ranked.walks[0]];
  const coordinates = selected.map((candidate, index) => [
    Number(candidate.lng ?? 140.8824 + index * 0.002),
    Number(candidate.lat ?? 38.2601 + index * 0.0015),
  ]) as Array<[number, number]>;
  return {
    legs: selected.slice(0, -1).map((candidate, index) => ({
      from: candidate.id,
      to: selected[index + 1].id,
      mode: index === 0 ? 'taxi' : 'walk',
      duration_minutes: index === 0 ? 12 : 8,
      distance_km: index === 0 ? 2.4 : 0.8,
      route_summary: index === 0 ? '打车降低换乘风险。' : '步行收尾，距离较短。',
    })),
    total_travel_minutes: 20,
    walking_distance_km: 0.8,
    drive_time_minutes: 12,
    polyline: { type: 'LineString' as const, coordinates },
    provider: 'local',
  };
}

function trace(agent: string, message: string, status: TraceSpan['status'], output_summary: Record<string, unknown> = {}) {
  return {
    id: `${agent}_${Date.now().toString(36)}`,
    agent,
    tool: agent,
    message,
    input_summary: {},
    output_summary,
    status,
    duration_ms: agent === 'parse_user_goal' ? 120 : 260,
    metadata: {},
  };
}

function toolCall(toolName: string, status: 'ok' | 'pending' = 'ok', outputSummary?: Record<string, unknown>) {
  return {
    id: `call_${toolName}`,
    tool: toolName,
    input_summary: {},
    output_summary: status === 'ok' ? { ok: true, ...outputSummary } : undefined,
    status,
    duration_ms: 180,
    side_effect: sideEffectTools.has(toolName),
  };
}
