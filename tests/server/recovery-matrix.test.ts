import test from 'node:test';
import assert from 'node:assert/strict';

import { buildPlan, recoverPlan } from '../../lib/server/planningService';

test('restaurant unavailable replaces only restaurant and preserves activity and dessert walk', async () => {
  const recovered = await recoverFixture('restaurant_unavailable');
  assert.equal(recovered.diff.changed, 'restaurant');
  const expected = recovered.previous.itinerary
    .filter((step: Record<string, any>) => step.type !== 'restaurant')
    .map((step: Record<string, any>) => step.title);
  assert.deepEqual(recovered.diff.preserved, expected);
});

test('activity full replaces activity and keeps restaurant when still valid', async () => {
  const recovered = await recoverFixture('activity_full');
  assert.equal(recovered.diff.changed, 'activity');
  const restaurantTitle = recovered.previous.itinerary.find((step: Record<string, any>) => step.type === 'restaurant')?.title;
  assert.ok(recovered.diff.preserved.includes(restaurantTitle));
});

test('rain switches outdoor nodes to indoor and marks rainy plan', async () => {
  const recovered = await recoverFixture('rain');
  assert.equal(recovered.plan.badges.includes('雨天方案'), true);
  assert.equal(recovered.plan.itinerary.some((step: Record<string, any>) => step.risk.includes('户外下雨')), false);
});

test('route timeout removes low priority node and exposes deleted reason', async () => {
  const recovered = await recoverFixture('route_timeout');
  assert.equal(recovered.diff.changed, 'route');
  assert.ok(recovered.diff.removed.some((item: Record<string, any>) => item.reason === 'route_timeout_low_priority'));
});

test('budget overrun returns cheaper version with coupon or lower price POI', async () => {
  const recovered = await recoverFixture('budget_overrun');
  assert.equal(recovered.diff.changed, 'budget');
  assert.ok(recovered.plan.overview.estimated_budget_value < recovered.previous.overview.estimated_budget_value);
});

test('constraint conflict returns healthy and relaxed alternatives', async () => {
  const recovered = await recoverFixture('constraint_conflict');
  assert.deepEqual(recovered.alternatives.map((item: Record<string, any>) => item.kind), ['healthy', 'relaxed']);
});

test('tool timeout retries once then falls back with visible retry trace', async () => {
  const recovered = await recoverFixture('tool_timeout');
  assert.equal(recovered.trace.some((step: Record<string, any>) => step.status === 'retrying'), true);
  assert.equal(recovered.trace.some((step: Record<string, any>) => step.status === 'fallback'), true);
});

async function recoverFixture(reason: string) {
  const plan = await buildPlan('今天下午 2 个成人和 1 个 5 岁孩子，14 点开始，玩 4.5 小时，想低脂低糖，别离家太远。');
  return recoverPlan(plan.plan.id, reason) as any;
}
