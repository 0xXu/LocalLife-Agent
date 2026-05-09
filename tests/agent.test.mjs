import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildPlan,
  executePlan,
  recoverUnavailableRestaurant,
  demoTools
} from './fixtures/legacyMockAgent.mjs';

test('buildPlan extracts family constraints and returns trace plus itinerary', () => {
  const result = buildPlan('Today afternoon is free, I want to go out with my wife and 5yo kid, not too far, wife is on a diet.');

  assert.equal(result.constraints.party, '2 位成人，1 位 5 岁儿童');
  assert.equal(result.constraints.dietary, '低脂友好');
  assert.equal(result.constraints.radiusKm, 5);
  assert.ok(result.trace.some((step) => step.tool === 'parse_user_goal'));
  assert.ok(result.trace.some((step) => step.tool === 'check_availability'));
  assert.equal(result.itinerary.length, 3);
  assert.equal(result.plan.status, 'ready_for_confirmation');
});

test('buildPlan exposes user-facing progress and confirmation actions', () => {
  const result = buildPlan('Today afternoon with my wife and 5yo kid, nearby, low fat food.');

  assert.deepEqual(result.progress.map((step) => step.label), [
    '理解出行需求',
    '筛选亲子活动',
    '匹配健康餐厅',
    '规划顺路路线',
    '确认可订时间'
  ]);
  assert.ok(result.progress.every((step) => step.status === 'done'));
  assert.equal(result.plan.title, '亲子科学馆 + 健康轻食半日计划');
  assert.equal(result.plan.itinerary[0].title, '城市科学馆');
  assert.deepEqual(result.plan.actions.map((action) => action.label), [
    '预约亲子活动',
    '预订轻食餐厅',
    '发送计划给家人'
  ]);
  assert.ok(result.plan.actions.every((action) => action.requiresConfirmation));
});

test('buildPlan recognizes Chinese child age with optional spacing', () => {
  const result = buildPlan('孩子 5 岁，老婆最近在减脂，别离家太远。');

  assert.equal(result.constraints.party, '2 位成人，1 位 5 岁儿童');
  assert.equal(result.constraints.dietary, '低脂友好');
  assert.equal(result.constraints.radiusKm, 5);
});

test('executePlan returns visible mock receipts for side-effect tools', () => {
  const result = executePlan(buildPlan('family low fat nearby').plan);

  assert.deepEqual(result.map((receipt) => receipt.type), [
    'activity_reservation',
    'restaurant_reservation',
    'message'
  ]);
  assert.match(result[0].id, /^TKT-/);
  assert.match(result[1].id, /^RES-/);
  assert.match(result[2].id, /^MSG-/);
});

test('recoverUnavailableRestaurant swaps only the restaurant and records a diff', () => {
  const original = buildPlan('family low fat nearby').plan;
  const recovered = recoverUnavailableRestaurant(original);

  assert.equal(recovered.diff.changed, 'restaurant');
  assert.equal(recovered.itinerary[0].placeId, original.itinerary[0].placeId);
  assert.notEqual(recovered.itinerary[1].placeId, original.itinerary[1].placeId);
  assert.equal(recovered.status, 'recovered_pending_confirmation');
  assert.equal(recovered.adjustment.headline, '餐厅临时无位，已为你换好备选');
  assert.equal(recovered.adjustment.primaryAction, '重新确认预订');
});

test('demoTools lists the eight mock tools promised in the submission', () => {
  assert.deepEqual(demoTools, [
    'parse_user_goal',
    'search_places',
    'search_restaurants',
    'rank_candidates',
    'optimize_route',
    'check_availability',
    'create_reservation',
    'send_plan_message'
  ]);
});
