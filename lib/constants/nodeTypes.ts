/**
 * 节点类型常量配置
 * 统一管理所有节点类型的标签、图标和描述
 */

export const NODE_TYPE_LABELS: Record<string, string> = {
  transport: '交通',
  activity: '活动',
  restaurant: '餐厅',
  dessert_walk: '散步',
};

export const NODE_TYPE_DESCRIPTIONS: Record<string, string> = {
  transport: '从当前位置出发',
  activity: '核心体验活动',
  restaurant: '用餐地点',
  dessert_walk: '饭后轻松步行',
};

export const ACTION_TYPE_LABELS: Record<string, string> = {
  reserve_activity: '预约活动',
  create_reservation: '预订餐厅',
  claim_coupon: '领取团购券',
  create_order: '创建点单',
  send_plan_message: '发送计划',
  create_calendar_event: '创建日历',
};

export const ACTION_TYPE_ICONS: Record<string, string> = {
  reserve_activity: 'ticket',
  create_reservation: 'utensils',
  claim_coupon: 'tag',
  create_order: 'shopping-bag',
  send_plan_message: 'message-square',
  create_calendar_event: 'calendar',
};

export const SCENARIO_LABELS: Record<string, string> = {
  family: '家庭',
  friends: '朋友',
  date: '约会',
  rainy_indoor: '雨天',
};

export const BUDGET_LABELS: Record<string, string> = {
  low: '省钱',
  medium: '适中',
  high: '不限',
};

export const DIET_LABELS: Record<string, string> = {
  low_fat: '低脂',
  low_sugar: '低糖',
  vegetarian: '素食',
  no_gluten: '无麸质',
};

export const VARIANT_KIND_LABELS: Record<string, string> = {
  main: '推荐',
  budget: '省钱',
  comfort: '舒适',
  child_first: '亲子',
  experience_first: '体验',
};

export const VARIANT_KIND_DESCRIPTIONS: Record<string, string> = {
  main: '综合距离、可订性和偏好匹配',
  budget: '优先使用团购券和低客单价餐厅',
  comfort: '减少步行和等待，优先高评分点位',
  child_first: '优先照顾活动体验和节奏',
  experience_first: '优先照顾活动体验和节奏',
};

export const RECOVERY_REASON_LABELS: Record<string, string> = {
  restaurant_unavailable: '餐厅无位',
  activity_full: '活动满员',
  route_timeout: '路线超时',
  budget_overrun: '预算超支',
  rain: '下雨',
};
