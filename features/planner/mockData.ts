// features/planner/mockData.ts
import type {
  PlanSummary,
  PlanListResponse,
  ActivityRecord,
  ActivityListResponse,
  UserPreferences,
} from '../../types/api';

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

const STORAGE_KEYS = {
  plans: 'weekendpilot_plans',
  preferences: 'weekendpilot_preferences',
} as const;

const MOCK_PLANS: PlanSummary[] = [
  {
    id: 'plan_001',
    title: '亲子科学馆半日游',
    status: 'saved',
    summary: '带孩子去科学馆探索互动展区，下午茶休息，公园散步放风。',
    created_at: '2026-05-08T10:00:00Z',
    updated_at: '2026-05-08T10:30:00Z',
    tags: ['家庭', '教育', '半日'],
    location: '市中心 5 公里内',
    estimated_cost: '约 320 元',
    itinerary_count: 4,
  },
  {
    id: 'plan_002',
    title: '朋友拍照聚餐',
    status: 'draft',
    summary: '艺术街区拍照打卡，创意菜餐厅聚餐，夜市散步。',
    created_at: '2026-05-07T15:00:00Z',
    updated_at: '2026-05-07T15:20:00Z',
    tags: ['朋友', '拍照', '预算适中'],
    location: '艺术街区',
    estimated_cost: '约 480 元',
    itinerary_count: 3,
  },
  {
    id: 'plan_003',
    title: '雨天室内备选',
    status: 'saved',
    summary: '室内攀岩体验，商场美食广场，电影院新片。',
    created_at: '2026-05-06T09:00:00Z',
    updated_at: '2026-05-06T09:15:00Z',
    tags: ['雨天', '室内', '低等待'],
    location: '商场室内动线',
    estimated_cost: '约 260 元',
    itinerary_count: 3,
  },
  {
    id: 'plan_004',
    title: '周末约会路线',
    status: 'completed',
    summary: '咖啡馆早午餐，美术馆展览，河滨散步晚餐。',
    created_at: '2026-05-03T11:00:00Z',
    updated_at: '2026-05-04T20:00:00Z',
    tags: ['约会', '文艺', '全天'],
    location: '河滨区域',
    estimated_cost: '约 580 元',
    itinerary_count: 5,
  },
];

const MOCK_ACTIVITIES: ActivityRecord[] = [
  {
    id: 'activity_001',
    plan_id: 'plan_004',
    plan_title: '周末约会路线',
    executed_at: '2026-05-04T10:00:00Z',
    status: 'completed',
    total_cost: '约 560 元',
    receipts: [
      { type: 'payment', tool: 'booking', id: 'r_001', status: 'success', detail: '咖啡馆早午餐预约成功，2人' },
      { type: 'payment', tool: 'booking', id: 'r_002', status: 'success', detail: '美术馆门票 2 张' },
      { type: 'payment', tool: 'booking', id: 'r_003', status: 'success', detail: '河滨餐厅晚餐预约，2人' },
    ],
    summary: '咖啡馆 + 美术馆 + 河滨晚餐',
  },
  {
    id: 'activity_002',
    plan_id: 'plan_old_001',
    plan_title: '雨天手作体验',
    executed_at: '2026-05-02T14:00:00Z',
    status: 'completed',
    total_cost: '约 320 元',
    receipts: [
      { type: 'payment', tool: 'booking', id: 'r_004', status: 'success', detail: '陶艺工坊体验预约成功' },
      { type: 'payment', tool: 'booking', id: 'r_005', status: 'success', detail: '邻近咖啡馆午餐' },
    ],
    summary: '陶艺体验 + 咖啡馆',
  },
  {
    id: 'activity_003',
    plan_id: 'plan_old_002',
    plan_title: '海岸自驾与海鲜',
    executed_at: '2026-04-28T10:00:00Z',
    status: 'completed',
    total_cost: '约 810 元',
    receipts: [
      { type: 'payment', tool: 'booking', id: 'r_006', status: 'success', detail: '海鲜餐厅预订确认' },
      { type: 'info', tool: 'navigation', id: 'r_007', status: 'success', detail: '海岸路线导航完成' },
    ],
    summary: '海岸自驾 + 海鲜大餐',
  },
  {
    id: 'activity_004',
    plan_id: 'plan_old_003',
    plan_title: '独立电影首映',
    executed_at: '2026-04-20T19:30:00Z',
    status: 'completed',
    total_cost: '约 245 元',
    receipts: [
      { type: 'payment', tool: 'booking', id: 'r_008', status: 'success', detail: '《霓虹回声》首映票 2 张' },
    ],
    summary: '独立电影 + 周边酒吧',
  },
];

const DEFAULT_PREFERENCES: UserPreferences = {
  profile: {
    display_name: '用户',
    email: 'user@example.com',
  },
  diet: {
    fitness_friendly: true,
    vegetarian: false,
    gluten_free: false,
    allergies: [],
  },
  location: {
    radius_km: 5,
    favorite_places: [],
  },
  notifications: {
    execution_reminder: true,
    plan_change: true,
    weekly_digest: false,
  },
};

export async function fetchPlans(): Promise<PlanListResponse> {
  await delay(800);
  const stored = localStorage.getItem(STORAGE_KEYS.plans);
  const plans: PlanSummary[] = stored ? JSON.parse(stored) : MOCK_PLANS;
  return { plans, total: plans.length };
}

export async function updatePlan(planId: string, updates: Partial<PlanSummary>): Promise<PlanSummary> {
  await delay(500);
  const stored = localStorage.getItem(STORAGE_KEYS.plans);
  const plans: PlanSummary[] = stored ? JSON.parse(stored) : [...MOCK_PLANS];
  const index = plans.findIndex((p) => p.id === planId);
  if (index === -1) throw new Error('Plan not found');
  plans[index] = { ...plans[index], ...updates, updated_at: new Date().toISOString() };
  localStorage.setItem(STORAGE_KEYS.plans, JSON.stringify(plans));
  return plans[index];
}

export async function deletePlan(planId: string): Promise<void> {
  await delay(400);
  const stored = localStorage.getItem(STORAGE_KEYS.plans);
  const plans: PlanSummary[] = stored ? JSON.parse(stored) : [...MOCK_PLANS];
  const filtered = plans.filter((p) => p.id !== planId);
  localStorage.setItem(STORAGE_KEYS.plans, JSON.stringify(filtered));
}

export async function fetchActivities(): Promise<ActivityListResponse> {
  await delay(600);
  return {
    activities: MOCK_ACTIVITIES,
    stats: {
      total_plans: MOCK_ACTIVITIES.length,
      total_cost: MOCK_ACTIVITIES.reduce(
        (sum, a) => sum + parseInt(a.total_cost?.replace(/\D/g, '') || '0'),
        0,
      ),
      frequent_type: '餐饮',
    },
  };
}

export async function fetchPreferences(): Promise<UserPreferences> {
  await delay(400);
  const stored = localStorage.getItem(STORAGE_KEYS.preferences);
  return stored ? JSON.parse(stored) : DEFAULT_PREFERENCES;
}

export async function savePreferences(prefs: UserPreferences): Promise<void> {
  await delay(300);
  localStorage.setItem(STORAGE_KEYS.preferences, JSON.stringify(prefs));
}
