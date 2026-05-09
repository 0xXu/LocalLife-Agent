import test from 'node:test';
import assert from 'node:assert/strict';

import { GET as getHealth } from '../../app/api/health/route';
import { GET as getToolSchemas } from '../../app/api/tool-schemas/route';
import { POST as buildPlan } from '../../app/api/plans/build/route';
import { GET as getPlan } from '../../app/api/plans/[planId]/route';
import { PATCH as patchConstraints } from '../../app/api/plans/[planId]/constraints/route';
import { POST as buildAlternatives } from '../../app/api/plans/[planId]/alternatives/route';
import { POST as confirmPlan } from '../../app/api/plans/[planId]/confirm/route';
import { POST as executePlan } from '../../app/api/plans/[planId]/execute/route';
import { POST as recoverPlan } from '../../app/api/plans/[planId]/recover/route';
import { GET as getTraces } from '../../app/api/traces/[planId]/route';

type RouteContext = { params: Promise<{ planId: string }> };

function jsonRequest(path: string, method = 'GET', body?: Record<string, unknown>) {
  return new Request(`http://localhost${path}`, {
    method,
    headers: body ? { 'content-type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
}

async function readJson(response: Response) {
  return response.json() as Promise<any>;
}

test('health and tool schemas routes expose stable service metadata', async () => {
  const health = await readJson(await getHealth());
  assert.equal(health.status, 'ok');
  assert.equal(health.service, 'weekendpilot-planner');

  const schemas = await readJson(await getToolSchemas());
  assert.deepEqual(schemas.tools.map((tool: { name: string }) => tool.name), [
    'parse_user_goal',
    'get_weather',
    'search_places',
    'search_restaurants',
    'check_availability',
    'optimize_route',
    'build_itinerary',
    'validate_plan',
    'compare_alternatives',
    'reserve_activity',
    'create_reservation',
    'claim_coupon',
    'create_order',
    'send_plan_message',
    'create_calendar_event',
  ]);
  assert.deepEqual(
    schemas.tools.filter((tool: { side_effect: boolean }) => tool.side_effect).map((tool: { name: string }) => tool.name),
    ['reserve_activity', 'create_reservation', 'claim_coupon', 'create_order', 'send_plan_message', 'create_calendar_event'],
  );
});

test('build, fetch, patch, alternatives, confirm, execute, recover, and traces routes return stable JSON', async () => {
  const buildResponse = await buildPlan(jsonRequest('/api/plans/build', 'POST', {
    goal: '今天下午朋友4个人出去玩，2男2女，先活动再吃饭，想拍照聊天，预算适中',
  }));
  assert.equal(buildResponse.status, 200);

  const build = await readJson(buildResponse);
  assert.equal(build.plan.status, 'pending_confirmation');
  assert.equal(build.plan.actions.length, 6);
  assert.ok(build.tool_calls.length >= 6);
  assert.equal(build.pending_actions.length, 6);
  assert.equal(build.itinerary.length, build.plan.itinerary.length);

  const planId = build.plan.id;
  const context: RouteContext = { params: Promise.resolve({ planId }) };

  const fetched = await readJson(await getPlan(jsonRequest(`/api/plans/${planId}`), context));
  assert.equal(fetched.plan.id, planId);

  const patched = await readJson(await patchConstraints(
    jsonRequest(`/api/plans/${planId}/constraints`, 'PATCH', { constraints: { radius_km: 4 } }),
    context,
  ));
  assert.equal(patched.constraints.constraints.radius_km, 4);

  const alternatives = await readJson(await buildAlternatives(
    jsonRequest(`/api/plans/${planId}/alternatives`, 'POST', {}),
    context,
  ));
  assert.ok(alternatives.variants.length >= 1);

  const confirmed = await readJson(await confirmPlan(
    jsonRequest(`/api/plans/${planId}/confirm`, 'POST', { confirmed: true }),
    context,
  ));
  assert.equal(confirmed.plan.status, 'confirmed');

  const executed = await readJson(await executePlan(
    jsonRequest(`/api/plans/${planId}/execute`, 'POST', { confirmed: true }),
    context,
  ));
  assert.deepEqual(executed.receipts.map((receipt: { type: string }) => receipt.type), [
    'activity_reservation',
    'restaurant_reservation',
    'coupon',
    'order',
    'message',
    'calendar',
  ]);
  assert.deepEqual(executed.receipts.map((receipt: { id: string }) => receipt.id.slice(0, 4)), [
    'TKT-',
    'RES-',
    'CPN-',
    'ORD-',
    'MSG-',
    'CAL-',
  ]);

  const recovered = await readJson(await recoverPlan(
    jsonRequest(`/api/plans/${planId}/recover`, 'POST', { reason: 'restaurant_unavailable' }),
    context,
  ));
  assert.equal(recovered.diff.changed, 'restaurant');
  assert.equal(recovered.plan.status, 'recovered_pending_confirmation');

  const traces = await readJson(await getTraces(jsonRequest(`/api/traces/${planId}`), context));
  assert.ok(traces.trace.length >= 1);
});
