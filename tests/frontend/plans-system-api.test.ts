import test from 'node:test';
import assert from 'node:assert/strict';

import { getPlan, listPlans } from '../../features/plans/api';
import { getLlmStatus, getToolSchemas } from '../../features/system/api';

type FetchCall = { url: string; init?: RequestInit };

function installFetch(body: Record<string, unknown>) {
  const calls: FetchCall[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return { ok: true, status: 200, json: async () => body } as Response;
  }) as typeof fetch;
  return calls;
}

test('plans and system API clients use the new route contract', async () => {
  delete process.env.NEXT_PUBLIC_API_URL;
  const calls = installFetch({ plans: [], total: 0, tools: [], provider: 'openai' });

  await listPlans();
  await getPlan('plan_1');
  await getToolSchemas();
  await getLlmStatus();

  assert.deepEqual(calls.map((call) => [call.url, call.init?.method ?? 'GET']), [
    ['http://127.0.0.1:8787/api/plans', 'GET'],
    ['http://127.0.0.1:8787/api/plans/plan_1', 'GET'],
    ['http://127.0.0.1:8787/api/tool-schemas', 'GET'],
    ['http://127.0.0.1:8787/api/llm/status', 'GET'],
  ]);
});
