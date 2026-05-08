export {
  buildPlan,
  demoTools,
  executePlan,
  recoverUnavailableRestaurant
} from '@/src/agent.mjs';

export const scenarioPrompts = {
  family: '今天下午是空的，想和老婆孩子出去玩几个小时，别离家太远。孩子 5 岁，老婆最近在减脂，帮我安排一下。',
  friends: '帮我安排一个轻松的朋友聚会，最好有适合拍照的活动、晚饭和饭后小酌，别太远。',
  rainy: '今天下午可能下雨，帮我找室内活动、舒服的餐厅和轻松路线。'
};

export const savedPlans = [
  {
    id: 'coastal_escape',
    title: '海边短途',
    date: '10 月 14 - 15 日',
    location: '海湾新区',
    status: '即将开始',
    tags: ['家庭', '放松', '预算适中'],
    accent: 'blue',
    imageClass: 'coast'
  },
  {
    id: 'art_district',
    title: '艺术街区漫游',
    date: '草稿',
    location: '市中心',
    status: '草稿',
    tags: ['文化', '步行', '省钱'],
    accent: 'violet',
    imageClass: 'street'
  },
  {
    id: 'mountain_retreat',
    title: '山间休整',
    date: '11 月 03 - 05 日',
    location: '山脉景区',
    status: '已保存',
    tags: ['自然', '活力'],
    accent: 'slate',
    imageClass: 'map'
  }
];

export const recentActivity = [
  {
    title: '雨天手作体验',
    meta: '昨天 · 14:00',
    status: '已完成',
    body: '陶艺工作坊体验顺利完成，老师反馈两件作品都提前完成。活动后的邻近咖啡馆午餐也按预订顺利入座。',
    links: ['查看回执（约 320 元）', '编号：#WKP-8921', '陶艺工坊']
  },
  {
    title: '海岸自驾与海鲜',
    meta: '2023 年 10 月 12 日 · 10:00',
    status: '已完成',
    body: '当天天气适合海岸路线，桥附近有轻微拥堵但整体顺畅。海鲜餐厅按时保留了订座。',
    links: ['查看回执（约 810 元）', '路线数据']
  },
  {
    title: '独立电影首映',
    meta: '2023 年 9 月 28 日 · 19:30',
    status: '已完成',
    body: '已为《霓虹回声》首映夜锁定票位。现场人流较多，但优先座位安排顺利。',
    links: ['查看回执（约 245 元）', '票务归档']
  }
];
