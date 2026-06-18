import test from 'node:test';
import assert from 'node:assert/strict';

import {
  ApproveActionsRequestSchema,
  CreateRunRequestSchema,
  CreateRunResponseSchema,
  RejectRunRequestSchema,
  RunEventEnvelopeSchema,
  RunEventTypeSchema,
  RunStatusResponseSchema,
  RunStatusSchema,
} from '../../features/runs/schemas';

test('run event envelope parses normalized SSE payloads', () => {
  const event = RunEventEnvelopeSchema.parse({
    type: 'approval.required',
    run_id: 'run_1',
    plan_id: 'plan_1',
    seq: 4,
    timestamp: '2026-06-19T00:00:00Z',
    payload: { actions: [] },
  });

  assert.equal(event.type, 'approval.required');
  assert.equal(event.payload.actions instanceof Array, true);
});

test('run status rejects old graph phases that are not product states', () => {
  assert.throws(() => RunStatusSchema.parse('pending_approval'));
  assert.equal(RunStatusSchema.parse('approval_required'), 'approval_required');
});

test('run contract schemas parse request and response payloads', () => {
  assert.equal(RunEventTypeSchema.parse('run.started'), 'run.started');
  assert.equal(CreateRunRequestSchema.parse({ goal: 'Plan my afternoon' }).user_id, 'local_demo_user');
  assert.equal(
    CreateRunResponseSchema.parse({
      run_id: 'run_1',
      plan_id: 'plan_1',
      status: 'queued',
      events_url: '/api/runs/run_1/events',
    }).status,
    'queued',
  );
  assert.equal(
    RunStatusResponseSchema.parse({
      run_id: 'run_1',
      plan_id: 'plan_1',
      status: 'running',
      created_at: '2026-06-19T00:00:00Z',
      updated_at: '2026-06-19T00:00:01Z',
    }).status,
    'running',
  );
  assert.deepEqual(ApproveActionsRequestSchema.parse({ action_ids: ['act_1'] }).action_ids, ['act_1']);
  assert.equal(RejectRunRequestSchema.parse({}).reason, 'user_rejected');
});
