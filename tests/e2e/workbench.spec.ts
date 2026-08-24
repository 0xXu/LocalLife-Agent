import { expect, test } from '@playwright/test';

const snapshot = {
  id: 'task_visual001',
  user_id: 'demo-user',
  goal_text: '今晚下班后想和朋友好好放松，预算 500，不想排队，23:00 前到家',
  phase: 'awaiting_mandate',
  revision: 4,
  messages: [
    { id: 'm1', role: 'agent', content: '我把地点集中在国贸，用一顿适合聊天的晚餐接喜剧演出，并预留了返程缓冲。', created_at: '2026-08-20T10:00:00Z' },
  ],
  goal: {
    outcome: '和朋友轻松度过今晚', city: '北京', origin: '国贸', party_size: 2,
    budget_yuan: 500, deadline: '23:00', preferences: ['少排队', '适合聊天'],
    constraints: [
      { id: 'c1', kind: 'budget', label: '总预算', value: '500 元以内', hard: true, source: 'explicit' },
      { id: 'c2', kind: 'deadline', label: '最晚到家', value: '23:00', hard: true, source: 'explicit' },
      { id: 'c3', kind: 'preference', label: '排队偏好', value: '不排队', hard: true, source: 'explicit' },
    ],
    assumptions: [{ id: 'a1', label: '出发位置', value: '国贸', reason: '按当前工作地点推断，可随时修改', editable: true }],
    open_questions: [], locked_fields: [],
  },
  question: null,
  plan: {
    version: 1, title: '国贸松弛喜剧夜', thesis: '短距离串联晚餐与喜剧，减少等待，把时间留给相处。',
    goal: null as unknown, total_yuan: 386,
    rationale: ['地点集中', '库存已核验'], tradeoffs: ['放弃更远但更新奇的手作活动'], locked_node_ids: [],
    mandate: { max_total_yuan: 500, deadline: '23:00', allowed_verticals: ['food', 'activity', 'mobility'], max_price_increase_yuan: 30, allow_auto_substitution: true, approved_at: null },
    updated_at: '2026-08-20T10:00:00Z',
    nodes: [
      { id: 'dinner', vertical: 'food', title: '宴岚·京味小馆', option_id: 'food_yanlan', starts_at: '18:40', ends_at: '20:00', price_yuan: 188, venue: '宴岚·京味小馆（国贸店）', reason: '有可预约桌位，安静且适合朋友聊天。', actions: ['buy_coupon', 'reserve_table'], status: 'proposed', depends_on: [], alternatives: ['food_monsoon'], evidence: { checked_at: '2026-08-20T10:00:00Z', detail: '桌位与餐券库存已核验', inventory_version: 3, valid_for_seconds: 300 } },
      { id: 'show', vertical: 'activity', title: '城市喜剧夜', option_id: 'activity_comedy', starts_at: '20:30', ends_at: '22:00', price_yuan: 156, venue: '开心麻花 A33 剧场', reason: '用轻松喜剧回应“好好放松”，场地离餐厅近。', actions: ['buy_ticket'], status: 'proposed', depends_on: ['dinner'], alternatives: ['activity_cinema'], evidence: { checked_at: '2026-08-20T10:00:00Z', detail: '中区连座剩余 8 张', inventory_version: 2, valid_for_seconds: 300 } },
      { id: 'home', vertical: 'mobility', title: '安心返程', option_id: 'mobility_home', starts_at: '22:10', ends_at: '22:42', price_yuan: 42, venue: '剧场 → 家', reason: '留出 18 分钟截止时间缓冲。', actions: ['request_ride'], status: 'proposed', depends_on: ['show'], alternatives: [], evidence: { checked_at: '2026-08-20T10:00:00Z', detail: '实时车型与预估价已核验', inventory_version: 4, valid_for_seconds: 300 } },
    ],
  },
  last_patch: null,
  pending_plan_edit: null,
  transaction_confirmation: null,
  fulfillment_events: [],
  reality_events: [],
  tool_traces: [
    { id: 't1', agent: 'capability_query_orchestrator', tool: 'food.search', input_summary: {}, status: 'succeeded', result_summary: '返回 1 条供给', world_version: 7, duration_ms: 214, occurred_at: '2026-08-20T10:00:00Z' },
  ],
  workflow_id: null,
  created_at: '2026-08-20T10:00:00Z', updated_at: '2026-08-20T10:00:00Z',
};

snapshot.plan.goal = snapshot.goal;
snapshot.plan.nodes.forEach((node) => Object.assign(node, {
  consumes_user_time: true,
  trigger_kind: node.vertical === 'food' ? 'queue_delay' : node.vertical === 'mobility' ? 'eta_delay' : 'inventory_unavailable',
}));
Object.assign(snapshot, {
  policy: {
    primary_plan: snapshot.plan,
    alternatives: [
      { candidate_id: 'candidate_2', direction: 'cheaper', summary: '少花 ¥48', total_yuan: 338, completion_time: '22:35', option_ids: ['food_monsoon', 'activity_cinema'] },
    ],
    decision_points: [
      { id: 'dp1', node_id: 'dinner', trigger: { kind: 'queue_delay', node_id: 'dinner', threshold: 30 }, slack_minutes: 30, decision_deadline: '18:10', fallbacks: [] },
    ],
  },
  feasible_plan_set: { status: 'feasible', pareto_candidate_ids: ['candidate_1', 'candidate_2'], infeasible_reasons: [] },
});
delete (snapshot as { plan?: unknown }).plan;

test('goal becomes an executable workbench', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('http://127.0.0.1:8787/api/tasks', (route) => route.fulfill({ json: snapshot }));
  await page.route('http://127.0.0.1:8787/api/preferences?user_id=demo-user', (route) => route.fulfill({ json: [] }));
  await page.route('http://127.0.0.1:8787/api/tasks/task_visual001/events', (route) => route.abort());
  await page.goto('/');
  await page.getByRole('button', { name: '开始安排' }).click();

  await expect(page.getByText('国贸松弛喜剧夜')).toBeVisible();
  await expect(page.getByText('查看代办边界')).toBeVisible();
  await page.getByRole('button', { name: /查看代办边界/ }).first().click();
  await expect(page.getByRole('dialog', { name: '代办边界' })).toBeVisible();
  await expect(page.getByRole('button', { name: '按这个边界开始办' })).toBeVisible();
  await page.getByRole('button', { name: '返回方案' }).click();
  await expect(page.getByText('宴岚·京味小馆', { exact: true })).toBeVisible();
  await expect(page.getByRole('navigation', { name: '任务视图' })).toBeVisible();
  await page.getByRole('button', { name: '目标' }).click();
  await expect(page.getByText(snapshot.goal_text, { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '编辑', exact: true }).click();
  await expect(page.getByRole('button', { name: /查看代办边界/ })).toHaveCount(0);
  await page.getByRole('button', { name: '取消', exact: true }).click();
  await page.getByRole('button', { name: '方案' }).click();
  await page.screenshot({ path: '/tmp/local-life-workbench.png', fullPage: true });
});

test('execution becomes a live companion instead of a planning trace', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const liveSnapshot = JSON.parse(JSON.stringify(snapshot));
  liveSnapshot.phase = 'completed';
  liveSnapshot.applied_preference_fact_ids = [];
  liveSnapshot.supply_signals = [];
  liveSnapshot.policy.primary_plan.nodes.forEach((node: { status: string }) => { node.status = 'completed'; });
  liveSnapshot.live = {
    next_step: null,
    risk: null,
    affected_node_ids: [],
    agent_activity: '本次生活目标已完成',
    waiting_for: null,
    available_actions: ['refund_ticket'],
    last_signal: null,
    actual_outcome: {
      total_yuan: 386,
      completed_node_ids: ['dinner', 'show', 'home'],
      compensated_node_ids: [],
      completed_at: '2026-08-20T14:00:00Z',
      summary: '现实履约结果已归档',
    },
    updated_at: '2026-08-20T14:00:00Z',
  };
  liveSnapshot.outcome_check_in = {
    prompt: '这次“和朋友轻松度过今晚”达到你想要的效果了吗？',
    response: null,
    note: null,
    responded_at: null,
  };
  await page.route('http://127.0.0.1:8787/api/tasks', (route) => route.fulfill({ json: liveSnapshot }));
  await page.route('http://127.0.0.1:8787/api/preferences?user_id=demo-user', (route) => route.fulfill({ json: [] }));
  await page.route('http://127.0.0.1:8787/api/tasks/task_visual001/events', (route) => route.abort());
  await page.goto('/');
  await page.getByRole('button', { name: '开始安排' }).click();

  await expect(page.getByTestId('live-mode')).toBeVisible();
  await expect(page.getByText('现场陪伴')).toBeVisible();
  await expect(page.getByTestId('live-mode').getByText('¥386')).toBeVisible();
  await expect(page.getByRole('button', { name: '退门票' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '达到了' })).toBeVisible();
});

test('answering a clarification immediately returns to visible planning progress', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const clarifying = JSON.parse(JSON.stringify(snapshot));
  clarifying.phase = 'clarifying';
  clarifying.policy = null;
  clarifying.question = {
    id: 'question-one',
    prompt: '今晚更想怎样放松？',
    why_now: '答案会改变供给方向。',
    options: [
      { id: 'quiet', label: '安静恢复', impact: '优先低体力体验' },
      { id: 'social', label: '轻松社交', impact: '优先适合聊天的体验' },
    ],
  };
  const replanning = JSON.parse(JSON.stringify(clarifying));
  replanning.phase = 'understanding';
  replanning.question = null;
  replanning.messages.push({ id: 'm2', role: 'user', content: '安静恢复', created_at: '2026-08-20T10:01:00Z' });

  await page.route('http://127.0.0.1:8787/api/tasks', (route) => route.fulfill({ json: clarifying }));
  await page.route('http://127.0.0.1:8787/api/tasks/task_visual001/messages', (route) => route.fulfill({ json: replanning }));
  await page.route('http://127.0.0.1:8787/api/preferences?user_id=demo-user', (route) => route.fulfill({ json: [] }));
  await page.route('http://127.0.0.1:8787/api/tasks/task_visual001/events', (route) => route.abort());
  await page.goto('/');
  await page.getByRole('button', { name: '开始安排' }).click();
  await page.getByRole('button', { name: /安静恢复/ }).click();

  await expect(page.getByRole('heading', { name: '理解目标', exact: true })).toBeVisible();
  await expect(page.locator('.planning-state').getByText('正在提取结果、约束与上下文', { exact: true })).toBeVisible();
});
