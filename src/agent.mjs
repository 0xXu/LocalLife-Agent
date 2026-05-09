// Legacy deterministic mock retained for historical tests only.
// The main product path uses Next.js API + LangGraph workflow + MCP-ready tools.
export const demoTools = [
  'parse_user_goal',
  'search_places',
  'search_restaurants',
  'rank_candidates',
  'optimize_route',
  'check_availability',
  'create_reservation',
  'send_plan_message'
];

const activity = {
  placeId: 'act_001',
  title: '城市科学馆',
  category: 'family_activity',
  start: '13:30',
  end: '15:30',
  cost: '约 320 元',
  travel: '打车 12 分钟',
  reason: '有“小小探索家”亲子展区，室内路线轻松，适合 5 岁孩子活动。'
};

const primaryRestaurant = {
  placeId: 'res_014',
  title: '绿荫轻食餐厅',
  category: 'restaurant',
  start: '15:45',
  end: '16:45',
  cost: '约 300 元',
  travel: '从科学馆步行 5 分钟',
  reason: '有沙拉、烤鸡胸和低脂标识菜单，同时提供儿童座椅。'
};

const fallbackRestaurant = {
  placeId: 'res_022',
  title: '轻碗健康餐厅',
  category: 'restaurant',
  start: '15:50',
  end: '16:50',
  cost: '约 340 元',
  travel: '从科学馆步行 7 分钟',
  reason: '同样提供低脂餐和儿童座椅，主餐厅无位后确认可订。'
};

const dessertWalk = {
  placeId: 'walk_006',
  title: '河畔低糖甜品散步',
  category: 'dessert_walk',
  start: '17:00',
  end: '17:30',
  cost: '约 130 元',
  travel: '轻松步行 1.2 公里',
  reason: '饭后短距离散步，沿路有低糖饮品选择，也方便直接回家。'
};

const progress = [
  {
    label: '理解出行需求',
    detail: '识别到家庭出行、5 岁儿童、半日空档、近距离和减脂饮食。',
    status: 'done'
  },
  {
    label: '筛选亲子活动',
    detail: '优先选择室内、轻松、适合 4-8 岁儿童的活动。',
    status: 'done'
  },
  {
    label: '匹配健康餐厅',
    detail: '交叉检查低脂菜单、儿童座椅和步行距离。',
    status: 'done'
  },
  {
    label: '规划顺路路线',
    detail: '把活动、餐厅和饭后散步压缩进 4 小时路线。',
    status: 'done'
  },
  {
    label: '确认可订时间',
    detail: '主餐厅 15:45 有 3 人模拟可订席位。',
    status: 'done'
  }
];

const confirmationActions = [
  {
    label: '预约亲子活动',
    target: activity.title,
    detail: '3 人入场名额，下午 13:30 到 15:30。',
    requiresConfirmation: true
  },
  {
    label: '预订轻食餐厅',
    target: primaryRestaurant.title,
    detail: '15:45，3 人桌位，低脂菜单优先。',
    requiresConfirmation: true
  },
  {
    label: '发送计划给家人',
    target: '家庭群聊',
    detail: '发送时间轴、路线和预算摘要。',
    requiresConfirmation: true
  }
];

export function buildPlan(goalText = '') {
  const constraints = {
    party: goalText.match(/5\s*y?o|5\s*岁|kid|child/i) ? '2 位成人，1 位 5 岁儿童' : '2 位成人',
    duration: '约 4.5 小时',
    dietary: goalText.match(/diet|low[-\s]?fat|减肥|减脂/i) ? '低脂友好' : '均衡饮食',
    radiusKm: goalText.match(/not too far|nearby|别.*远|5km/i) ? 5 : 8,
    transport: '打车 + 步行'
  };

  const itinerary = [activity, primaryRestaurant, dessertWalk].map((step) => ({ ...step }));
  const plan = {
    id: 'plan_family_001',
    status: 'ready_for_confirmation',
    title: '亲子科学馆 + 健康轻食半日计划',
    summary: '科学馆亲子活动、低脂轻食餐厅和饭后河畔散步。',
    constraints,
    itinerary,
    overview: {
      theme: '下午 · 家庭 · 健康轻松',
      totalDuration: '4 小时',
      driveTime: '约 25 分钟',
      walkingDistance: '1.2 公里',
      estimatedCost: '约 750 - 900 元'
    },
    actions: confirmationActions.map((action) => ({ ...action }))
  };

  const trace = [
    traceStep('parse_user_goal', '解析出家庭、饮食、距离和半日时长约束。', 'ok'),
    traceStep('search_places', '找到 5 公里内适合亲子的室内外活动。', 'ok'),
    traceStep('search_restaurants', '匹配附近带低脂菜单标识的餐厅。', 'ok'),
    traceStep('rank_candidates', '按距离、儿童友好、饮食匹配、等待时间和预算排序。', 'ok'),
    traceStep('optimize_route', '生成科学馆 -> 轻食餐厅 -> 河畔散步路线。', 'ok'),
    traceStep('check_availability', '绿荫轻食餐厅 15:45 有 3 人模拟可订席位。', 'ok')
  ];

  return {
    constraints,
    progress: progress.map((step) => ({ ...step })),
    trace,
    itinerary,
    plan
  };
}

export function executePlan(plan) {
  const targetPlan = plan ?? buildPlan().plan;

  return [
    {
      type: 'activity_reservation',
      tool: 'create_reservation',
      id: 'TKT-2041',
      status: '已确认',
      detail: `已为 3 人预约${targetPlan.itinerary[0].title}。`
    },
    {
      type: 'restaurant_reservation',
      tool: 'create_reservation',
      id: restaurantReceiptId(targetPlan.itinerary[1].placeId),
      status: '已确认',
      detail: `已预订${targetPlan.itinerary[1].title} ${targetPlan.itinerary[1].start} 的 3 人桌。`
    },
    {
      type: 'message',
      tool: 'send_plan_message',
      id: 'MSG-9128',
      status: '已发送',
      detail: '计划摘要已发送到家庭群聊。'
    }
  ];
}

export function recoverUnavailableRestaurant(plan) {
  const original = plan ?? buildPlan().plan;
  const itinerary = original.itinerary.map((step, index) => (
    index === 1 ? { ...fallbackRestaurant } : { ...step }
  ));

  return {
    ...original,
    id: 'plan_family_001_recovered',
    status: 'recovered_pending_confirmation',
    itinerary,
    actions: original.actions.map((action, index) => (
      index === 1
        ? {
            ...action,
            target: fallbackRestaurant.title,
            detail: '15:50，3 人桌位，低脂菜单备选已确认。'
          }
        : { ...action }
    )),
    diff: {
      changed: 'restaurant',
      reason: '绿荫轻食餐厅返回该时段无位。',
      from: original.itinerary[1].title,
      to: fallbackRestaurant.title,
      costDelta: '+约 40 元',
      travelDelta: '+步行 2 分钟',
      preserved: [original.itinerary[0].title, original.itinerary[2].title]
    },
    adjustment: {
      headline: '餐厅临时无位，已为你换好备选',
      message: `${primaryRestaurant.title}当前时段无位，已替换为步行 7 分钟可达的${fallbackRestaurant.title}。原亲子活动和饭后散步保持不变。`,
      primaryAction: '重新确认预订',
      secondaryAction: '换另一家餐厅'
    }
  };
}

function traceStep(tool, message, status) {
  return {
    tool,
    status,
    message,
    durationMs: tool === 'parse_user_goal' ? 120 : 260
  };
}

function restaurantReceiptId(placeId) {
  return placeId === fallbackRestaurant.placeId ? 'RES-7420' : 'RES-3812';
}
