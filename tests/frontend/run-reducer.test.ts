import test from 'node:test';
import assert from 'node:assert/strict';

import { initialRunState, runReducer } from '../../features/runs/reducer';

const clarificationQuestion = {
  id: 'time_window',
  label: '今天下午大概几点开始？',
  kind: 'time',
  required: true,
  options: [{ label: '今天下午 2 点', value: '今天下午 2 点' }],
  allow_custom: true,
};

test('run reducer moves through planning to approval required', () => {
  const started = runReducer(initialRunState, {
    type: 'run.started',
    run_id: 'run_1',
    plan_id: 'plan_1',
    seq: 1,
    timestamp: '2026-06-19T00:00:00Z',
    payload: { status: 'running' },
  });
  const approval = runReducer(started, {
    type: 'approval.required',
    run_id: 'run_1',
    plan_id: 'plan_1',
    seq: 2,
    timestamp: '2026-06-19T00:00:01Z',
    payload: { actions: [{ action_id: 'act_1' }] },
  });

  assert.equal(approval.runId, 'run_1');
  assert.equal(approval.planId, 'plan_1');
  assert.equal(approval.status, 'approval_required');
  assert.equal(approval.pendingActions.length, 1);
});

test('run reducer stores the current clarification question', () => {
  const clarified = runReducer(initialRunState, {
    type: 'clarification.required',
    run_id: 'run_1',
    plan_id: 'plan_1',
    seq: 1,
    timestamp: '2026-06-19T00:00:00Z',
    payload: { question: clarificationQuestion },
  });

  assert.equal(clarified.status, 'needs_clarification');
  assert.deepEqual(clarified.currentQuestion, clarificationQuestion);
});

for (const eventType of ['run.started', 'agent.started', 'run.completed', 'run.failed', 'run.rejected'] as const) {
  test(`run reducer clears current clarification question on ${eventType}`, () => {
    const clarification = runReducer(initialRunState, {
      type: 'clarification.required',
      run_id: 'run_1',
      plan_id: 'plan_1',
      seq: 1,
      timestamp: '2026-06-19T00:00:00Z',
      payload: { question: clarificationQuestion },
    });

    const next = runReducer(clarification, {
      type: eventType,
      run_id: 'run_1',
      plan_id: 'plan_1',
      seq: 2,
      timestamp: '2026-06-19T00:00:01Z',
      payload: {},
    });

    assert.equal(next.currentQuestion, null);
  });
}

test('run reducer clears pending actions on terminal failure states', () => {
  const approval = runReducer(initialRunState, {
    type: 'approval.required',
    run_id: 'run_1',
    plan_id: 'plan_1',
    seq: 1,
    timestamp: '2026-06-19T00:00:00Z',
    payload: { actions: [{ action_id: 'act_1' }] },
  });

  const failed = runReducer(approval, {
    type: 'run.failed',
    run_id: 'run_1',
    plan_id: 'plan_1',
    seq: 2,
    timestamp: '2026-06-19T00:00:01Z',
    payload: { error: 'tool_failed' },
  });
  const invalid = runReducer(approval, {
    type: 'guardrail.triggered',
    run_id: 'run_1',
    plan_id: 'plan_1',
    seq: 3,
    timestamp: '2026-06-19T00:00:02Z',
    payload: { reason: 'invalid_plan' },
  });

  assert.equal(failed.status, 'failed');
  assert.equal(failed.pendingActions.length, 0);
  assert.equal(invalid.status, 'validation_failed');
  assert.equal(invalid.pendingActions.length, 0);
});

test('run reducer ignores duplicate replayed SSE events', () => {
  const event = {
    type: 'run.started' as const,
    run_id: 'run_1',
    plan_id: 'plan_1',
    seq: 1,
    timestamp: '2026-06-19T00:00:00Z',
    payload: { status: 'running' },
  };

  const started = runReducer(initialRunState, event);
  const replayed = runReducer(started, event);

  assert.equal(replayed.events.length, 1);
  assert.equal(replayed.status, 'running');
});
