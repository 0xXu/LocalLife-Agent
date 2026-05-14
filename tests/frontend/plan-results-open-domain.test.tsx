import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { PlanResultsView } from '../../components/plan/PlanResultsView';

test('plan results renders Python backend open-domain variants and fit metrics', () => {
  const html = renderToStaticMarkup(
    <PlanResultsView
      result={makeOpenDomainResponse() as any}
      selectedActions={new Set(['act_msg_001'])}
      executing={false}
      onToggleAction={() => {}}
      onSelectAll={() => {}}
      onDeselectAll={() => {}}
      onApprove={() => {}}
      onReject={() => {}}
      error={null}
    />,
  );

  assert.match(html, /宠物散步短计划/);
  assert.match(html, /省钱版/);
  assert.match(html, /约束匹配/);
  assert.match(html, /距离/);
  assert.match(html, /预算/);
  assert.match(html, /local_seed_route_matrix/);
  assert.match(html, /候选解释/);
  assert.match(html, /偏好匹配高/);
  assert.match(html, /Action Ledger/);
  assert.match(html, /批准执行/);
});

test('plan results falls back to revision constraints from graph-run payloads', () => {
  const response = makeOpenDomainResponse();
  const { constraints, ...withoutTopLevelConstraints } = response;
  const html = renderToStaticMarkup(
    <PlanResultsView
      result={{
        ...withoutTopLevelConstraints,
        revision: {
          revision_id: 'rev_graph_001',
          phase: 'pending_approval',
          constraints,
          plan: response.plan,
        },
      } as any}
      selectedActions={new Set(['act_msg_001'])}
      executing={false}
      onToggleAction={() => {}}
      onSelectAll={() => {}}
      onDeselectAll={() => {}}
      onApprove={() => {}}
      onReject={() => {}}
      error={null}
    />,
  );

  assert.match(html, /宠物散步短计划/);
  assert.match(html, /8km/);
});

function makeOpenDomainResponse() {
  const itinerary = [{
    start: '14:00',
    end: '15:50',
    type: 'activity',
    title: '宠物友好河岸公园1号店',
    place_id: 'poi_007',
    reason: '允许牵绳宠物进入，路面平缓。',
    cost: '约 325 元',
    travel: '到达活动点',
    score: 95,
    risk: '风险低。',
  }];
  return {
    constraints: {
      scenario: 'pet_friendly_walk',
      origin: { type: 'current_location', label: 'home', lat: 38.2601, lng: 140.8824 },
      time_window: { date: 'today', start: '14:00', duration_hours: 3, flexible: true },
      people: { adults: 1, children: [], relationship: 'solo' },
      preferences: { distance: 'nearby', diet: [], activity: ['pet', 'outdoor', 'walkable'], budget_level: 'medium', intent_label: '宠物散步' },
      constraints: { radius_km: 8, max_wait_minutes: 15, avoid: ['long_queue'] },
      required_actions: ['send_plan_message', 'create_calendar_event'],
    },
    progress: [],
    trace: [],
    tool_calls: [],
    candidate_sets: {
      activities: [{
        place: {
          id: 'poi_007',
          name: '宠物友好河岸公园1号店',
          distance_km: 1.2,
          wait_minutes: 3,
          source: 'local_seed_catalog',
          provenance: { source: 'local_seed_catalog' },
        },
        total_score: 0.92,
        score_breakdown: { semantic: 0.32, distance: 0.18, quality: 0.18, wait: 0.1, budget: 0.12, provenance: 0.06 },
        explanation: '偏好匹配高。',
      }],
    },
    validation_issues: [],
    route: {
      legs: [],
      total_travel_minutes: 0,
      walking_distance_km: 0,
      drive_time_minutes: 12,
      polyline: { type: 'LineString', coordinates: [[140.8791, 38.2618], [140.8811, 38.2638]] },
      provider: 'local_seed_route_matrix',
    },
    pending_actions: [],
    actions: [{ action_id: 'act_msg_001', type: 'send_plan_message', tool: 'messaging', label: '发送计划', detail: '发送摘要', status: 'pending', payload: {} }],
    plan: {
      id: 'plan_open_001',
      status: 'pending_confirmation',
      title: '宠物散步短计划',
      summary: '围绕“宠物散步”选择本地供给，按时间、距离、预算和可执行动作生成计划。',
      constraint_fit: { distance: 0.95, time: 1, budget: 0.92 },
      itinerary,
      overview: { theme: '下午 · pet friendly walk · 可执行', totalDuration: '3 小时', driveTime: '约 12 分钟', walkingDistance: '0.0 公里', estimatedCost: '约 325 元', score: 98 },
      actions: [{ action_id: 'act_msg_001', type: 'send_plan_message', tool: 'messaging', label: '发送计划', detail: '发送摘要', status: 'pending', payload: {} }],
      variants: [
        { id: 'variant_main', kind: 'main', title: '主方案', summary: '综合距离、可订性和偏好匹配。', score: 98, estimated_budget: 325, constraint_fit: { distance: 0.95, time: 1, budget: 0.92 }, itinerary },
        { id: 'variant_budget', kind: 'budget', title: '省钱版', summary: '优先使用低客单价点位。', score: 93, estimated_budget: 300, constraint_fit: { distance: 0.9, time: 1, budget: 1 }, itinerary },
      ],
      receipts: [],
      badges: ['宠物散步', 'pet', 'outdoor', '轻量短计划'],
    },
    receipts: [],
  };
}
