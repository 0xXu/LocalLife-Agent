import test from 'node:test';
import assert from 'node:assert/strict';

import { createSpan, recordToolCall, startWeekendPilotTelemetry } from '../../lib/observability/otel';
import { normalizeTraceEvents } from '../../lib/observability/tracing';
import { createCheckpointerAdapter, createTestCheckpointRepository } from '../../lib/data/repositories/checkpointRepository';
import { createTestTraceRepository } from '../../lib/data/repositories/traceRepository';

test('checkpoint repository can persist and reload graph state by thread id', async () => {
  const repo = createTestCheckpointRepository();
  await repo.save({ thread_id: 'thread_001', status: 'USER_CONFIRMATION', state_json: { pending_actions: [1, 2, 3] } });

  const loaded = await repo.load('thread_001');

  assert.equal(loaded?.status, 'USER_CONFIRMATION');
  assert.deepEqual(loaded?.state_json.pending_actions, [1, 2, 3]);
});

test('checkpoint repository exposes a LangGraph-compatible checkpointer adapter', async () => {
  const repo = createTestCheckpointRepository();
  const checkpointer = createCheckpointerAdapter(repo);

  await checkpointer.put('thread_002', {
    thread_id: 'thread_002',
    status: 'USER_CONFIRMATION',
    clarifying_questions: [],
    receipts: [],
    pending_side_effects: [{ id: 'action_1' }],
  });

  const loaded = await checkpointer.get('thread_002');
  assert.equal(loaded?.status, 'USER_CONFIRMATION');
  assert.equal(loaded?.pending_side_effects[0].id, 'action_1');
});

test('trace repository stores tool logs, retry logs, and receipt ids', async () => {
  const repo = createTestTraceRepository();

  await repo.append('plan_001', { tool: 'create_reservation', status: 'retrying', error: { code: 'timeout' } });
  await repo.append('plan_001', { tool: 'create_reservation', status: 'ok', side_effect: true, output_summary: { id: 'RES-1' } });
  const trace = await repo.list('plan_001');
  const executions = await repo.listExecutions('plan_001');

  assert.equal(trace[0].status, 'retrying');
  assert.equal(trace[1].output_summary.id, 'RES-1');
  assert.equal(executions[0].receipt.id, 'RES-1');
});

test('normalized trace events can be persisted without losing side-effect ids', async () => {
  const events = normalizeTraceEvents({
    trace: [{ agent: 'Executor', tool: 'create_order', status: 'retrying', message: '第一次超时', error: 'timeout' }],
    tool_calls: [{ tool: 'send_plan_message', status: 'ok', side_effect: true, output_summary: { id: 'MSG-1' } }],
  });

  assert.equal(events[0].status, 'retrying');
  assert.equal(events[1].side_effect, true);
  assert.equal(events[1].output_summary.id, 'MSG-1');
});

test('OpenTelemetry boundary is a no-op when telemetry env vars are absent', () => {
  const telemetry = startWeekendPilotTelemetry({});
  const span = createSpan('planner.test', { plan_id: 'plan_001' }, {});
  const recorded = recordToolCall('planner.tool', { tool: 'parse_user_goal', status: 'ok', input_summary: {}, side_effect: false }, {});

  span.setAttribute('status', 'ok');
  span.end();

  assert.equal(telemetry.enabled, false);
  assert.equal(span.name, 'planner.test');
  assert.equal(recorded.enabled, false);
});
