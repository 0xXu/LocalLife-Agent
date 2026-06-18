import test from 'node:test';
import assert from 'node:assert/strict';

import { initialRunState, runReducer } from '../../features/runs/reducer';

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
