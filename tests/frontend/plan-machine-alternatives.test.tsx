import test from 'node:test';
import assert from 'node:assert/strict';

import { mergePlanAlternatives } from '../../features/planner/usePlanMachine';

test('mergePlanAlternatives preserves the current plan when alternatives endpoint returns variants only', () => {
  const current = {
    plan: {
      id: 'plan_001',
      status: 'pending_confirmation',
      itinerary: [{ type: 'activity', title: '徒步路线' }],
      actions: [],
    },
    variants: [{ kind: 'main', title: '主方案' }],
  } as any;
  const alternatives = {
    plan_id: 'plan_001',
    alternatives: [{ kind: 'comfort', title: '舒适方案' }],
    variants: [{ kind: 'comfort', title: '舒适方案' }],
  } as any;

  const merged = mergePlanAlternatives(current, alternatives);

  assert.equal(merged.plan.id, 'plan_001');
  assert.equal(merged.plan.itinerary[0].title, '徒步路线');
  assert.deepEqual(merged.variants.map((variant: any) => variant.kind), ['main', 'comfort']);
});
