import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildAlternatives,
  buildPlan,
  confirmPlan,
  executePlan,
  getHealth,
  getPlan,
  listPlans,
  getToolSchemas,
  getTraces,
  patchConstraints,
  recoverPlan,
} from '../../features/planner/apiClient';

type FetchCall = {
  url: string;
  init?: RequestInit;
};

function installFetch(body: Record<string, unknown>, ok = true) {
  const calls: FetchCall[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return {
      ok,
      status: ok ? 200 : 500,
      statusText: ok ? 'OK' : 'Server Error',
      json: async () => body,
    } as Response;
  }) as typeof fetch;
  return calls;
}

test('planner API client serializes request bodies and methods', async () => {
  delete process.env.NEXT_PUBLIC_API_URL;
  const calls = installFetch({ plan: { id: 'plan_client_001' } });

  await buildPlan('家庭半日计划');
  await listPlans();
  await getPlan('plan_client_001');
  await patchConstraints('plan_client_001', { constraints: { radius_km: 4 } });
  await buildAlternatives('plan_client_001');
  await confirmPlan('plan_client_001');
  await executePlan('plan_client_001');
  await recoverPlan('plan_client_001', 'restaurant_unavailable');
  await getTraces('plan_client_001');
  await getToolSchemas();
  await getHealth();

  assert.deepEqual(calls.map((call) => [call.url, call.init?.method ?? 'GET']), [
    ['http://127.0.0.1:8787/api/plans/build', 'POST'],
    ['http://127.0.0.1:8787/api/plans', 'GET'],
    ['http://127.0.0.1:8787/api/plans/plan_client_001', 'GET'],
    ['http://127.0.0.1:8787/api/plans/plan_client_001/constraints', 'PATCH'],
    ['http://127.0.0.1:8787/api/plans/plan_client_001/alternatives', 'POST'],
    ['http://127.0.0.1:8787/api/plans/plan_client_001/confirm', 'POST'],
    ['http://127.0.0.1:8787/api/plans/plan_client_001/execute', 'POST'],
    ['http://127.0.0.1:8787/api/plans/plan_client_001/recover', 'POST'],
    ['http://127.0.0.1:8787/api/traces/plan_client_001', 'GET'],
    ['http://127.0.0.1:8787/api/tool-schemas', 'GET'],
    ['http://127.0.0.1:8787/api/health', 'GET'],
  ]);

  assert.equal(calls[0].init?.body, JSON.stringify({ goal: '家庭半日计划' }));
  assert.equal(calls[3].init?.body, JSON.stringify({ constraints: { radius_km: 4 } }));
  assert.equal(calls[5].init?.body, JSON.stringify({ confirmed: true }));
  assert.equal(calls[6].init?.body, JSON.stringify({ confirmed: true }));
  assert.equal(calls[7].init?.body, JSON.stringify({ reason: 'restaurant_unavailable' }));
  assert.equal((calls[0].init?.headers as Record<string, string>)['content-type'], 'application/json');
});

test('planner API client uses NEXT_PUBLIC_API_URL when configured', async () => {
  process.env.NEXT_PUBLIC_API_URL = 'http://backend.local:8787/';
  const calls = installFetch({ plan: { id: 'plan_client_002' } });

  await buildPlan('custom backend');

  assert.equal(calls[0].url, 'http://backend.local:8787/api/plans/build');
  delete process.env.NEXT_PUBLIC_API_URL;
});

test('planner API client throws response details for failed requests', async () => {
  installFetch({ error: { code: 'plan_not_found', message: 'Missing plan' } }, false);

  await assert.rejects(
    () => getPlan('missing'),
    /plan_not_found: Missing plan/,
  );
});

test('planner API client preserves flat Python backend error details', async () => {
  installFetch({ error: 'confirmation_required' }, false);

  await assert.rejects(
    () => executePlan('plan_client_001'),
    /confirmation_required: confirmation_required/,
  );
});
