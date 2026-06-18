import test from 'node:test';
import assert from 'node:assert/strict';

import { approveRunActions, createRun, rejectRun } from '../../features/runs/api';

type FetchCall = { url: string; init?: RequestInit };

function installFetch(body: Record<string, unknown>) {
  const calls: FetchCall[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return { ok: true, status: 200, json: async () => body } as Response;
  }) as typeof fetch;
  return calls;
}

test('run API client uses run-centered endpoints', async () => {
  delete process.env.NEXT_PUBLIC_API_URL;
  const calls = installFetch({ run_id: 'run_1', plan_id: 'plan_1', status: 'queued', events_url: '/api/runs/run_1/events' });

  await createRun({ goal: '家庭半日计划', user_id: 'user_1', mode: 'plan' });
  await approveRunActions('run_1', ['act_1']);
  await rejectRun('run_1', 'user_rejected');

  assert.deepEqual(calls.map((call) => [call.url, call.init?.method ?? 'GET']), [
    ['http://127.0.0.1:8787/api/runs', 'POST'],
    ['http://127.0.0.1:8787/api/runs/run_1/actions/approve', 'POST'],
    ['http://127.0.0.1:8787/api/runs/run_1/actions/reject', 'POST'],
  ]);
  assert.equal(calls[0].init?.body, JSON.stringify({ goal: '家庭半日计划', user_id: 'user_1', mode: 'plan' }));
});
