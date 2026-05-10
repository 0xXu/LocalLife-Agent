export const scenarioPrompts = {
  family: '今天下午是空的，想和老婆孩子出去玩几个小时，别离家太远。孩子 5 岁，老婆最近在减脂，帮我安排一下。',
  friends: '今天下午朋友 4 个人出去玩，2 男 2 女，先活动再吃饭，想拍照聊天，预算适中，路线顺一点。',
  date: '下午想和对象约会，安静一点，有氛围，排队少，饭前饭后都顺，别安排太累。',
  rainy: '今天下午可能下雨，帮我找室内活动、舒服的餐厅和轻松路线。'
};

export const savedPlans = [
  {
    id: 'family_science_half_day',
    title: '亲子科学馆半日',
    date: '今天 14:00 - 18:30',
    location: '市中心 5 公里内',
    status: '待执行',
    tags: ['家庭', '减脂友好', '半日'],
    accent: 'blue',
    imageClass: 'map'
  },
  {
    id: 'friends_photo_dinner',
    title: '朋友拍照聚餐',
    date: '周六 15:00 - 20:00',
    location: '艺术街区',
    status: '草稿',
    tags: ['朋友', '拍照', '预算适中'],
    accent: 'violet',
    imageClass: 'street'
  },
  {
    id: 'rainy_indoor_backup',
    title: '雨天室内备选',
    date: '周日 13:30 - 18:00',
    location: '商场室内动线',
    status: '已保存',
    tags: ['雨天', '室内', '低等待'],
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
