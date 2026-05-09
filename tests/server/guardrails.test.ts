import test from 'node:test';
import assert from 'node:assert/strict';

import { executeActionsNode } from '../../lib/agent/nodes/executeActions';
import { ensureKnownPlaceIds } from '../../lib/agent/guardrails';
import { redactPrivateText } from '../../lib/privacy/redaction';

test('guardrails block hallucinated place ids', () => {
  assert.throws(
    () => ensureKnownPlaceIds({ itinerary: [{ place_id: 'invented_001' }] }, new Set(['r_014'])),
    /unknown_place_id:invented_001/,
  );
});

test('side effects require confirmation snapshot', async () => {
  await assert.rejects(
    () => executeActionsNode(makeExecutionState(), { confirmed: true, confirmationSnapshot: null }),
    /confirmation_snapshot_required/,
  );
});

test('privacy redaction removes phone, email, precise address, and raw contact identifiers', () => {
  const redacted = redactPrivateText('发给 xiaoran@example.com，手机号 13812345678，地址 青叶区一番町1-2-3');
  assert.equal(redacted.includes('xiaoran@example.com'), false);
  assert.equal(redacted.includes('13812345678'), false);
  assert.equal(redacted.includes('一番町1-2-3'), false);
});

function makeExecutionState() {
  return {
    thread_id: 'thread_guardrail',
    status: 'EXECUTE_ACTIONS',
    confirmed: true,
    clarifying_questions: [],
    receipts: [],
    pending_side_effects: [{ tool: 'create_reservation' }],
    plan_response: {
      constraints: {
        scenario: 'family',
        origin: { type: 'current_location', label: 'home', lat: 38.2601, lng: 140.8824 },
        time_window: { date: '2026-05-09', start: '14:00', duration_hours: 4.5, flexible: true },
        people: { adults: 2, children: [{ age: 5 }], relationship: 'family' },
        preferences: { distance: 'nearby', diet: [], activity: [], budget_level: 'medium' },
        constraints: { radius_km: 5, max_wait_minutes: 15, avoid: [] },
        required_actions: [],
      },
      progress: [],
      trace: [],
      tool_calls: [],
      pending_actions: [],
      plan: {
        id: 'plan_guardrail',
        status: 'pending_confirmation',
        title: 'Plan',
        summary: 'Plan',
        constraint_fit: { distance: 1, time: 1, budget: 1 },
        itinerary: [],
        overview: { theme: 'Plan', totalDuration: '4.5 小时', driveTime: '0', walkingDistance: '0', estimatedCost: '0', score: 90 },
        actions: [],
        variants: [],
        receipts: [],
        badges: [],
      },
      actions: [],
      variants: [],
      receipts: [],
    },
  };
}
