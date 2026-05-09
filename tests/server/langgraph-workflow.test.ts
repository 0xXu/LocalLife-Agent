import test from 'node:test';
import assert from 'node:assert/strict';

import { createPlannerGraph, createTestCheckpointer } from '../../lib/agent/graph';
import { PlanStatuses } from '../../lib/agent/state';
import { buildPlan, executePlan } from '../../lib/server/planningService';

const completeGoal = '今天下午想和老婆孩子出去玩几个小时，别离家太远，吃得健康一点。孩子 5 岁，14 点开始，玩 4.5 小时。';

test('graph pauses at USER_CONFIRMATION and resumes with the same thread id', async () => {
  const checkpointer = createTestCheckpointer();
  const graph = createPlannerGraph({ checkpointer });
  const config = { configurable: { thread_id: 'thread_confirm_001' } };

  const paused = await graph.invoke({ goal: completeGoal }, config);

  assert.equal(paused.thread_id, 'thread_confirm_001');
  assert.equal(paused.status, PlanStatuses.USER_CONFIRMATION);
  assert.equal(paused.plan_response.plan.status, 'pending_confirmation');
  assert.equal(paused.plan_response.receipts.length, 0);
  assert.equal(paused.plan_response.pending_actions.length, 6);

  const resumed = await graph.invoke({ confirmed: true }, config);

  assert.equal(resumed.thread_id, 'thread_confirm_001');
  assert.equal(resumed.status, PlanStatuses.DONE);
  assert.equal(resumed.plan_response.plan.status, 'completed');
  assert.equal(resumed.plan_response.receipts.length, 6);
  assert.equal(resumed.plan_response.plan.receipts.length, 6);
});

test('graph records NEED_CLARIFICATION when goal lacks time and people', async () => {
  const graph = createPlannerGraph({ checkpointer: createTestCheckpointer() });

  const result = await graph.invoke(
    { goal: '想在附近安排一个轻松一点的半日计划，吃得健康一点。' },
    { configurable: { thread_id: 'thread_clarify_001' } },
  );

  assert.equal(result.status, PlanStatuses.NEED_CLARIFICATION);
  assert.deepEqual(result.clarifying_questions, ['几个人出行？', '希望从几点开始、玩多久？']);
  assert.equal(result.plan_response, undefined);
  assert.equal(result.receipts.length, 0);
  assert.equal(result.pending_side_effects.length, 0);
});

test('planningService facade preserves build and execute response compatibility', async () => {
  const built = await buildPlan(completeGoal);

  assert.equal(built.plan.status, 'pending_confirmation');
  assert.equal(built.pending_actions.length, 6);
  assert.equal(built.receipts.length, 0);

  const executed = await executePlan(built.plan.id, true);

  assert.equal(executed.plan.status, 'completed');
  assert.equal(executed.receipts.length, 6);
  assert.deepEqual(executed.receipts.map((receipt) => receipt.type), [
    'activity_reservation',
    'restaurant_reservation',
    'coupon',
    'order',
    'message',
    'calendar',
  ]);
});
