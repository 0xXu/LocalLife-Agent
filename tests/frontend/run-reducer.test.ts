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
