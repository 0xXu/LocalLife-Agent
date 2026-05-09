import { v7 as uuidv7 } from 'uuid';

import { PlanResponseSchema } from '../../contracts/schemas';
import type { PlanAction, PlanResponse, Receipt, TraceSpan } from '../../../types/weekendpilot';
import { PlanStatuses, type PlannerState, sideEffectTools } from '../state';

export function buildItinerary(state: PlannerState): PlannerState {
  const plan_response = makePlanResponse(state);
  return {
    ...state,
    status: PlanStatuses.BUILD_ITINERARY,
    plan_response,
    pending_side_effects: plan_response.pending_actions,
  };
}

export function makePlanResponse(state: Pick<PlannerState, 'constraints' | 'goal' | 'thread_id'>): PlanResponse {
  const constraints = state.constraints;
  if (!constraints) {
    throw new Error('Cannot build itinerary before constraints are parsed.');
  }

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

function toolCall(toolName: string, status: 'ok' | 'pending' = 'ok') {
  return {
    id: `call_${toolName}`,
    tool: toolName,
    input_summary: {},
    output_summary: status === 'ok' ? { ok: true } : undefined,
    status,
    duration_ms: 180,
    side_effect: sideEffectTools.has(toolName),
  };
}
