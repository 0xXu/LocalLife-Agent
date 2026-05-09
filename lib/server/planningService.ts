import { PlanResponseSchema } from '../contracts/schemas';
import { createPlannerGraph, createTestCheckpointer } from '../agent/graph';
import { applyRecoveryPolicy, isRecoveryReason } from '../recovery/recoveryPolicies';
import type { ParsedConstraints, PlanAction, PlanResponse, Receipt, TraceSpan } from '../../types/weekendpilot';

export type ServiceErrorCode = 'validation_error' | 'confirmation_required' | 'plan_not_found' | 'tool_failed';

export class PlanningServiceError extends Error {
  code: ServiceErrorCode;

  constructor(code: ServiceErrorCode, message: string) {
    super(message);
    this.code = code;
  }
}

type PlanningServiceStore = {
  plans: Map<string, Record<string, any>>;
  planThreads: Map<string, string>;
};

declare global {
  // Keep dev-route module reloads from dropping in-flight demo plans.
  // Task 18 replaces this runtime cache boundary with repository persistence.
  var __weekendPilotPlanningServiceStore: PlanningServiceStore | undefined;
}

const serviceStore = globalThis.__weekendPilotPlanningServiceStore ??= {
  plans: new Map<string, Record<string, any>>(),
  planThreads: new Map<string, string>(),
};

const plans = serviceStore.plans;
const planThreads = serviceStore.planThreads;
const plannerCheckpointer = createTestCheckpointer();
const plannerGraph = createPlannerGraph({ checkpointer: plannerCheckpointer });

const defaultGoal = '今天下午想和家人出去玩几个小时，别离家太远，吃得健康一点。';

export const scenarioPrompts = {
  family: '今天下午是空的，想和老婆孩子出去玩几个小时，别离家太远。孩子 5 岁，老婆最近在减脂，帮我安排一下。',
  friends: '今天下午朋友 4 个人出去玩，2 男 2 女，先活动再吃饭，想拍照聊天，预算适中，路线顺一点。',
  date: '下午想和对象约会，安静一点，有氛围，排队少，饭前饭后都顺，别安排太累。',
  rainy: '今天下午可能下雨，帮我找室内活动、舒服的餐厅和轻松路线。',
};

export function getHealth() {
  return {
    status: 'ok',
    service: 'weekendpilot-planner',
    mode: 'temporary-typescript-service',
  };
}

export function getToolSchemas() {
  return {
    tools: [
      tool('parse_user_goal', 'Extract scenario, party, time, budget, and hard constraints.'),
      tool('get_weather', 'Fetch local weather for the requested time window.'),
      tool('search_places', 'Find grounded local activities, dessert, walk, and indoor places inside the configured radius.'),
      tool('search_restaurants', 'Find restaurants with availability and menu fit.'),
      tool('check_availability', 'Check restaurant seats or activity capacity for the requested party size.'),
      tool('optimize_route', 'Generate route legs, total travel minutes, and walking distance.'),
      tool('build_itinerary', 'Build the executable 4 to 6 hour itinerary from ranked candidates.'),
      tool('validate_plan', 'Validate opening hours, route duration, budget, and availability.'),
      tool('compare_alternatives', 'Compare original and recovered plans and return a visible diff.'),
      tool('reserve_activity', 'Reserve activity tickets after user confirmation.', true),
      tool('create_reservation', 'Create restaurant reservations after user confirmation.', true),
      tool('claim_coupon', 'Claim applicable local coupon after user confirmation.', true),
      tool('create_order', 'Create a pickup or light pre-order after user confirmation.', true),
      tool('send_plan_message', 'Send plan summary to selected recipients after confirmation.', true),
      tool('create_calendar_event', 'Create calendar event after confirmation.', true),
    ],
  };
}

export async function buildPlan(goal = defaultGoal) {
  const threadId = `service_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
  const state = await plannerGraph.invoke(
    { goal },
    { configurable: { thread_id: threadId } },
  );

  if (!state.plan_response) {
    throw new PlanningServiceError('validation_error', state.clarifying_questions.join(' ') || 'Plan needs clarification.');
  }

  const response = state.plan_response;
  plans.set(response.plan.id, response);
  planThreads.set(response.plan.id, threadId);
  return response;
}

export function getPlan(planId: string) {
  return requirePlan(planId);
}

export function patchConstraints(planId: string, patch: Record<string, any>) {
  const current = requirePlan(planId);
  const nextConstraints = {
    ...current.constraints,
    ...(patch ?? {}),
    constraints: {
      ...current.constraints.constraints,
      ...(patch?.constraints ?? {}),
    },
    preferences: {
      ...current.constraints.preferences,
      ...(patch?.preferences ?? {}),
    },
  };
  const next = {
    ...current,
    constraints: nextConstraints,
    trace: current.trace.concat(trace('constraint_editor', '用户更新了约束，计划等待重新确认。', 'ok')),
  };
  plans.set(planId, next);
  return next;
}

export function buildAlternatives(planId: string) {
  const current = requirePlan(planId);
  const next = {
    ...current,
    variants: current.plan.variants,
    plan: {
      ...current.plan,
      variants: current.plan.variants,
    },
    trace: current.trace.concat(trace('alternative_builder', '已生成雨天和低预算备选方案。', 'ok')),
  };
  plans.set(planId, next);
  return next;
}

export function confirmPlan(planId: string, confirmed: boolean) {
  if (!confirmed) {
    throw new PlanningServiceError('confirmation_required', 'Plan confirmation is required.');
  }
  return updatePlan(planId, { status: 'confirmed' });
}

export async function executePlan(planId: string, confirmed: boolean) {
  if (!confirmed) {
    throw new PlanningServiceError('confirmation_required', 'Plan confirmation is required before execution.');
  }
  const current = requirePlan(planId);
  const threadId = planThreads.get(planId);
  if (!threadId) {
    throw new PlanningServiceError('plan_not_found', `Plan thread not found: ${planId}`);
  }

  const state = await plannerGraph.invoke(
    { confirmed: true, plan_response: current as PlanResponse },
    { configurable: { thread_id: threadId } },
  );

  if (!state.plan_response) {
    throw new PlanningServiceError('tool_failed', state.error ?? 'Plan execution failed.');
  }

  const next = state.plan_response;
  plans.set(planId, next);
  return next;
}

export function recoverPlan(planId: string, reason: string) {
  const current = requirePlan(planId);
  if (!isRecoveryReason(reason)) {
    throw new PlanningServiceError('validation_error', `Unsupported recovery reason: ${reason}`);
  }

  const next = applyRecoveryPolicy(current, reason);
  plans.set(planId, next);
  plans.set(next.plan.id, next);
  const threadId = planThreads.get(planId);
  if (threadId) {
    planThreads.set(next.plan.id, threadId);
  }
  return next;
}

export function getTraces(planId: string) {
  const current = requirePlan(planId);
  return {
    planId,
    trace: current.trace,
    tool_calls: current.tool_calls,
  };
}

function updatePlan(planId: string, values: Record<string, any>) {
  const current = requirePlan(planId);
  const next = {
    ...current,
    plan: {
      ...current.plan,
      ...values,
    },
    trace: current.trace.concat(trace('confirmation_gate', '用户已确认计划。', 'ok')),
  };
  plans.set(planId, next);
  return next;
}

function requirePlan(planId: string) {
  const plan = plans.get(planId);
  if (!plan) {
    throw new PlanningServiceError('plan_not_found', `Plan not found: ${planId}`);
  }
  return plan;
}

function makePlanResponse(goal: string) {
  const constraints = makeConstraints(goal);
  const itinerary = [
    {
      id: 'step_activity',
      place_id: 'act_001',
      placeId: 'act_001',
      type: 'family_activity',
      category: 'family_activity',
      title: '城市科学馆',
      start: '14:00',
      end: '15:40',
      cost: '约 320 元',
      travel: '打车 12 分钟',
      risk: ['weekend_queue'],
      reason: '有亲子探索展区，室内路线轻松，适合 5 岁孩子活动。',
    },
    {
      id: 'step_restaurant',
      place_id: 'res_014',
      placeId: 'res_014',
      type: 'restaurant',
      category: 'restaurant',
      title: '绿荫轻食餐厅',
      start: '15:55',
      end: '16:55',
      cost: '约 300 元',
      travel: '从科学馆步行 5 分钟',
      risk: ['limited_tables'],
      reason: '有低脂套餐、儿童座椅和低糖饮品，当前等待时间低于 15 分钟。',
    },
    {
      id: 'step_walk',
      place_id: 'walk_006',
      placeId: 'walk_006',
      type: 'dessert_walk',
      category: 'dessert_walk',
      title: '河畔低糖甜品散步',
      start: '17:10',
      end: '17:40',
      cost: '约 130 元',
      travel: '轻松步行 1.2 公里',
      risk: [],
      reason: '饭后短距离散步，沿路有低糖饮品选择，也方便直接回家。',
    },
  ];
  const actions = makeActions();
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
      trace('rank_candidates', '按距离、儿童友好、饮食匹配、等待时间和预算排序。', 'ok'),
      trace('optimize_route', '生成科学馆 -> 轻食餐厅 -> 河畔散步路线。', 'ok'),
      trace('check_availability', '绿荫轻食餐厅 15:55 有 3 人模拟可订席位。', 'ok'),
    ],
    tool_calls: [
      toolCall('parse_user_goal'),
      toolCall('search_local_activities'),
      toolCall('search_restaurants'),
      toolCall('rank_candidates'),
      toolCall('optimize_route'),
      toolCall('check_availability'),
      toolCall('reserve_activity'),
      toolCall('create_reservation'),
      toolCall('claim_coupon'),
      toolCall('create_order'),
      toolCall('send_plan_message'),
      toolCall('create_calendar_event'),
    ],
    pending_actions: actions.map((action, index) => ({
      id: `pending_${index + 1}`,
      type: action.type,
      tool: action.tool ?? action.type,
      label: action.label ?? action.type,
      requires_confirmation: true,
      payload: action.payload,
    })),
    itinerary,
    plan: {
      id: `plan_${Date.now().toString(36)}`,
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
        estimatedCost: '约 750 - 900 元',
        score: 91,
        estimated_budget_value: 850,
      },
      actions,
      variants: [
        {
          id: 'variant_rainy',
          kind: 'rainy_indoor',
          title: '雨天室内备选',
          summary: '把河畔散步替换为商场室内甜品和儿童书店。',
          constraint_fit: { distance: 0.9, child_friendly: 1, diet: 0.82, time: 0.9, budget: 0.84 },
          itinerary: [],
          actions: [],
        },
      ],
      receipts: [],
      badges: ['5 公里内', '儿童友好', '低脂菜单', '可执行'],
    },
    actions,
    variants: [],
    receipts: [],
  };

  PlanResponseSchema.parse(response);
  return response;
}

function makeConstraints(goal: string): ParsedConstraints & Record<string, any> {
  return {
    scenario: goal.includes('朋友') ? 'friends' : 'family',
    origin: { type: 'current_location', label: 'home', lat: 38.2601, lng: 140.8824 },
    time_window: { date: '2026-05-09', start: '14:00', duration_hours: 4.5, flexible: true },
    people: { adults: goal.includes('朋友') ? 4 : 2, children: goal.includes('朋友') ? [] : [{ age: 5 }], relationship: goal.includes('朋友') ? 'friends' : 'family' },
    preferences: {
      distance: 'nearby',
      diet: ['low_fat', 'low_sugar'],
      activity: goal.includes('朋友') ? ['photo_spot', 'chat'] : ['child_friendly', 'not_too_tiring'],
      budget_level: 'medium',
    },
    constraints: { radius_km: 5, max_wait_minutes: 15, avoid: ['heavy_oil', 'long_queue', 'smoking'] },
    required_actions: ['activity_reservation', 'restaurant_reservation', 'send_plan_message'],
    party: goal.includes('朋友') ? '4 位朋友' : '2 位成人，1 位 5 岁儿童',
    duration: '约 4.5 小时',
    dietary: '低脂友好',
    radiusKm: 5,
    transport: '打车 + 步行',
  };
}

function makeActions(): Array<PlanAction & Record<string, any>> {
  return [
    action('activity_reservation', 'reserve_activity', '预约亲子活动', '城市科学馆', '3 人入场名额，下午 14:00 到 15:40。'),
    action('restaurant_reservation', 'create_reservation', '预订轻食餐厅', '绿荫轻食餐厅', '15:55，3 人桌位，低脂菜单优先。'),
    action('coupon', 'claim_coupon', '领取餐饮优惠券', '绿荫轻食餐厅', '领取低脂套餐 9 折券。'),
    action('order', 'create_order', '预点低糖饮品', '河畔甜品店', '预留下单低糖饮品和儿童点心。'),
    action('message', 'send_plan_message', '发送计划给家人', '家庭群聊', '发送时间轴、路线和预算摘要。'),
    action('calendar', 'create_calendar_event', '写入日历', '家庭日历', '创建 14:00 到 17:40 的半日计划。'),
  ];
}

function action(type: string, toolName: string, label: string, target: string, detail: string): PlanAction & Record<string, any> {
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

function makeReceipts(planResponse: Record<string, any>): Receipt[] {
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

function trace(agent: string, message: string, status: TraceSpan['status']) {
  return {
    id: `${agent}_${Date.now().toString(36)}`,
    agent,
    tool: agent,
    message,
    input_summary: {},
    status,
    duration_ms: agent === 'parse_user_goal' ? 120 : 260,
    metadata: {},
  };
}

function toolCall(toolName: string) {
  return {
    id: `call_${toolName}`,
    tool: toolName,
    input_summary: {},
    output_summary: { ok: true },
    status: 'ok' as const,
    duration_ms: 180,
    side_effect: ['reserve_activity', 'create_reservation', 'claim_coupon', 'create_order', 'send_plan_message', 'create_calendar_event'].includes(toolName),
  };
}

function tool(name: string, description: string, sideEffect = false) {
  return {
    name,
    description,
    side_effect: sideEffect,
    input_schema: {
      type: 'object',
      additionalProperties: true,
    },
  };
}
