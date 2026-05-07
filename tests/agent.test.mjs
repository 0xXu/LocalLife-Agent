import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildPlan,
  executePlan,
  recoverUnavailableRestaurant,
  demoTools
} from '../src/agent.mjs';

test('buildPlan extracts family constraints and returns trace plus itinerary', () => {
  const result = buildPlan('Today afternoon is free, I want to go out with my wife and 5yo kid, not too far, wife is on a diet.');

  assert.equal(result.constraints.party, '2 adults, 1 child (5yo)');
  assert.equal(result.constraints.dietary, 'low-fat');
  assert.equal(result.constraints.radiusKm, 5);
  assert.ok(result.trace.some((step) => step.tool === 'parse_user_goal'));
  assert.ok(result.trace.some((step) => step.tool === 'check_availability'));
  assert.equal(result.itinerary.length, 3);
  assert.equal(result.plan.status, 'ready_for_confirmation');
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

