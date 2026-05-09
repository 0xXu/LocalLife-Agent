import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { BottomExecutionBar } from '../../components/planner/BottomExecutionBar';
import { ConstraintCards } from '../../components/planner/ConstraintCards';
import { PlanCanvas } from '../../components/planner/PlanCanvas';
import { PromptComposer } from '../../components/planner/PromptComposer';

test('planner workbench renders input, constraints, trace, plan canvas, map, and bottom execution bar', () => {
  const html = renderPlannerWorkbench(makePlanResponseFixture());
  assert.match(html, /今天下午/);
  assert.match(html, /人群/);
  assert.match(html, /Agent 执行轨迹/);
  assert.match(html, /主方案/);
  assert.match(html, /地图与路线/);
  assert.match(html, /确认执行/);
});

test('constraint cards render as editable controls', () => {
  const html = renderToStaticMarkup(<ConstraintCards planId="plan_test" constraints={makePlanResponseFixture().constraints} />);
  assert.match(html, /data-constraint="radius_km"/);
  assert.match(html, /data-constraint="budget_level"/);
  assert.match(html, /data-constraint="start"/);
  assert.match(html, /data-constraint="diet"/);
});

test('bottom execution bar lists six detailed design actions', () => {
  const html = renderToStaticMarkup(<BottomExecutionBar actions={makePlanResponseFixture().plan.actions} />);
  for (const label of ['预约活动', '预订餐厅', '领取团购券', '创建点单', '发送计划', '创建日历']) {
    assert.match(html, new RegExp(label));
  }
});

function renderPlannerWorkbench(fixture: ReturnType<typeof makePlanResponseFixture>) {
  return renderToStaticMarkup(
    <main className="planner-workbench">
      <PromptComposer goal="今天下午 2 个成人和 1 个 5 岁孩子，14 点开始，想轻松玩 4.5 小时" />
      <ConstraintCards planId={fixture.plan.id} constraints={fixture.constraints} />
      <PlanCanvas response={fixture} />
      <BottomExecutionBar actions={fixture.plan.actions} />
    </main>,
  );
}

function makePlanResponseFixture() {
  const constraints = {
    scenario: 'family',
    origin: { type: 'current_location', label: 'home', lat: 38.2601, lng: 140.8824 },
    time_window: { date: '2026-05-09', start: '14:00', duration_hours: 4.5, flexible: true },
    people: { adults: 2, children: [{ age: 5 }], relationship: 'family' },
    preferences: { distance: 'nearby', diet: ['low_fat', 'low_sugar'], activity: ['child_friendly'], budget_level: 'medium' },
    constraints: { radius_km: 5, max_wait_minutes: 15, avoid: [] },
    required_actions: [],
    party: '2 位成人，1 位 5 岁儿童',
    duration: '约 4.5 小时',
    dietary: '低脂友好',
    radiusKm: 5,
  };
  const itinerary = [
    { id: 'step_1', place_id: 'poi_activity', type: 'family_activity', title: '青叶亲子科学工坊', start: '14:00', end: '15:30', reason: '儿童友好且室内动线短。', risk: [] },
    { id: 'step_2', place_id: 'poi_restaurant', type: 'restaurant', title: '青叶低脂食堂', start: '15:50', end: '16:50', reason: '低脂低糖菜单可用。', risk: ['limited_tables'] },
  ];
  const actions = [
    { type: 'activity_reservation', tool: 'reserve_activity', label: '预约亲子活动', target: '青叶亲子科学工坊', detail: '14:00 入场', requires_confirmation: true, payload: {} },
    { type: 'restaurant_reservation', tool: 'create_reservation', label: '预订餐厅', target: '青叶低脂食堂', detail: '15:50 三人桌', requires_confirmation: true, payload: {} },
    { type: 'coupon', tool: 'claim_coupon', label: '领取团购券', target: '青叶低脂食堂', detail: '低脂套餐券', requires_confirmation: true, payload: {} },
    { type: 'order', tool: 'create_order', label: '创建点单', target: '青叶低脂食堂', detail: '预点低糖饮品', requires_confirmation: true, payload: {} },
    { type: 'message', tool: 'send_plan_message', label: '发送计划', target: '家庭群聊', detail: '发送摘要', requires_confirmation: true, payload: {} },
    { type: 'calendar', tool: 'create_calendar_event', label: '创建日历', target: '家庭日历', detail: '写入 14:00-17:40', requires_confirmation: true, payload: {} },
  ];

  return {
    constraints,
    trace: [
      { id: 'trace_1', agent: 'Planner', tool: 'parse_user_goal', message: '解析用户目标', input_summary: {}, output_summary: {}, status: 'ok' },
      { id: 'trace_2', agent: 'Planner', tool: 'rank_candidates', message: '排序候选', input_summary: {}, output_summary: { rejected_reasons: [] }, status: 'ok' },
    ],
    tool_calls: [],
    progress: [],
    pending_actions: [],
    plan: {
      id: 'plan_test',
      status: 'pending_confirmation',
      title: '家庭半日计划',
      summary: '本地半日生活方案',
      constraint_fit: { distance: 0.94, child_friendly: 0.98, diet: 0.92, time: 0.9, budget: 0.86 },
      itinerary,
      overview: { theme: '下午 · 家庭', totalDuration: '4.5 小时', driveTime: '约 25 分钟', walkingDistance: '1.2 公里', estimatedCost: '约 7200 円', score: 91 },
      actions,
      variants: [
        { id: 'variant_main', kind: 'main', title: '主方案', itinerary, actions: [], overview: { theme: '主方案', totalDuration: '4.5 小时', driveTime: '约 25 分钟', walkingDistance: '1.2 公里', estimatedCost: '约 7200 円', score: 91 } },
        { id: 'variant_budget', kind: 'budget', title: '预算优先', itinerary: [itinerary[1], itinerary[0]], actions: [], overview: { theme: '预算优先', totalDuration: '4.5 小时', driveTime: '约 25 分钟', walkingDistance: '1.2 公里', estimatedCost: '约 5600 円', score: 84 } },
      ],
      receipts: [],
      badges: [],
    },
    actions,
    variants: [],
    receipts: [],
  };
}
