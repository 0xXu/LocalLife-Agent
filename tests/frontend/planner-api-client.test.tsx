import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getHealth,
  getPlan,
  getPlanVersions,
  listPlans,
  rejectPlan,
  resumePlan,
  streamRunUpdates,
  getToolSchemas,
  getTraces,
  startPlanRun,
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

test('planner API client uses graph-run workflow endpoints', async () => {
  delete process.env.NEXT_PUBLIC_API_URL;
  const calls = installFetch({ plan: { id: 'plan_client_001' }, run_id: 'run_1', thread_id: 'thread_1', plan_id: 'plan_client_001' });

  await startPlanRun('家庭半日计划', 'local_demo_user');
  await listPlans();
  await getPlan('plan_client_001');
  await resumePlan('plan_client_001', ['act_msg_001']);
  await rejectPlan('plan_client_001');
  await getPlanVersions('plan_client_001');
  await getTraces('plan_client_001');
  await getToolSchemas();
  await getHealth();

  assert.deepEqual(calls.map((call) => [call.url, call.init?.method ?? 'GET']), [
    ['http://127.0.0.1:8787/api/plans/runs', 'POST'],
    ['http://127.0.0.1:8787/api/plans', 'GET'],
    ['http://127.0.0.1:8787/api/plans/plan_client_001', 'GET'],
    ['http://127.0.0.1:8787/api/plans/plan_client_001/resume', 'POST'],
    ['http://127.0.0.1:8787/api/plans/plan_client_001/resume', 'POST'],
    ['http://127.0.0.1:8787/api/plans/plan_client_001/versions', 'GET'],
    ['http://127.0.0.1:8787/api/traces/plan_client_001', 'GET'],
    ['http://127.0.0.1:8787/api/tool-schemas', 'GET'],
    ['http://127.0.0.1:8787/api/health', 'GET'],
  ]);

  assert.equal(calls[0].init?.body, JSON.stringify({ goal: '家庭半日计划', user_id: 'local_demo_user' }));
  assert.equal(calls[3].init?.body, JSON.stringify({ decision: 'approve', selected_action_ids: ['act_msg_001'] }));
  assert.equal(calls[4].init?.body, JSON.stringify({ decision: 'reject' }));
  assert.equal((calls[0].init?.headers as Record<string, string>)['content-type'], 'application/json');
});

test('planner API client uses NEXT_PUBLIC_API_URL when configured', async () => {
  process.env.NEXT_PUBLIC_API_URL = 'http://backend.local:8787/';
  const calls = installFetch({ plan: { id: 'plan_client_002' } });

  await startPlanRun('custom backend');

  assert.equal(calls[0].url, 'http://backend.local:8787/api/plans/runs');
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
    () => resumePlan('plan_client_001', ['act_msg_001']),
    /confirmation_required: confirmation_required/,
  );
});

test('streamRunUpdates closes compact graph streams after the first graph update', async () => {
  const originalEventSource = globalThis.EventSource;
  const instances: FakeEventSource[] = [];
  class FakeEventSource {
    static CLOSED = 2;
    readyState = 1;
    closed = false;
    listeners: Record<string, Array<(event: MessageEvent) => void>> = {};

    constructor(public url: string) {
      instances.push(this);
    }

    addEventListener(type: string, listener: (event: MessageEvent) => void) {
      this.listeners[type] = [...(this.listeners[type] ?? []), listener];
    }

    close() {
      this.closed = true;
      this.readyState = FakeEventSource.CLOSED;
    }

    emit(type: string, data: unknown) {
      for (const listener of this.listeners[type] ?? []) {
        listener({ data: JSON.stringify(data) } as MessageEvent);
      }
    }
  }
  globalThis.EventSource = FakeEventSource as unknown as typeof EventSource;

  let receivedPhase = '';
  const stop = streamRunUpdates('run_1', {
    onGraphUpdate: (event) => {
      receivedPhase = event.phase;
    },
  });
  instances[0].emit('graph_update', {
    run_id: 'run_1',
    thread_id: 'thread_1',
    plan_id: 'plan_1',
    revision_id: 'rev_1',
    phase: 'pending_approval',
    is_final: true,
    revision: {
      revision_id: 'rev_1',
      phase: 'pending_approval',
      plan: {
        id: 'plan_1',
        status: 'pending_approval',
        title: '计划',
        summary: '摘要',
        constraint_fit: { distance: 1, time: 1, budget: 1 },
        itinerary: [],
        overview: { theme: '下午', totalDuration: '2 小时', driveTime: '约 10 分钟', walkingDistance: '0 公里', estimatedCost: '¥100', score: 80 },
        actions: [],
        receipts: [],
        badges: [],
      },
    },
  });

  assert.equal(receivedPhase, 'pending_approval');
  assert.equal(instances[0].closed, true);
  stop();
  globalThis.EventSource = originalEventSource;
});
