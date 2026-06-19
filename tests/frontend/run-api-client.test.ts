import test from 'node:test';
import assert from 'node:assert/strict';

import { approveRunActions, createRun, rejectRun, streamRunEvents, submitClarification } from '../../features/runs/api';

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
  await submitClarification('run_1', { question_id: 'time_window', answer: '今天下午 2 点' });

  assert.deepEqual(calls.map((call) => [call.url, call.init?.method ?? 'GET']), [
    ['http://127.0.0.1:8787/api/runs', 'POST'],
    ['http://127.0.0.1:8787/api/runs/run_1/actions/approve', 'POST'],
    ['http://127.0.0.1:8787/api/runs/run_1/actions/reject', 'POST'],
    ['http://127.0.0.1:8787/api/runs/run_1/clarifications', 'POST'],
  ]);
  assert.equal(calls[0].init?.body, JSON.stringify({ goal: '家庭半日计划', user_id: 'user_1', mode: 'plan' }));
  assert.equal(calls[3].init?.body, JSON.stringify({ question_id: 'time_window', answer: '今天下午 2 点' }));
});

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  readyState = 0;
  closeCount = 0;
  listeners: Record<string, Array<(event: MessageEvent) => void>> = {};

  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    this.listeners[type] = [...(this.listeners[type] ?? []), listener];
  }

  emit(type: string, data: Record<string, unknown>) {
    for (const listener of this.listeners[type] ?? []) {
      listener({ data: JSON.stringify(data) } as MessageEvent);
    }
  }

  close() {
    this.closeCount += 1;
  }
}

for (const terminalType of ['run.completed', 'run.failed', 'run.rejected'] as const) {
  test(`streamRunEvents listens to named run.event frames and closes on ${terminalType}`, () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    FakeEventSource.instances = [];
    globalThis.EventSource = FakeEventSource as unknown as typeof EventSource;
    const received: string[] = [];

    streamRunEvents('run_1', {
      onEvent: (event) => {
        received.push(event.type);
      },
    });

    const source = FakeEventSource.instances[0];
    assert.equal(source.url, 'http://127.0.0.1:8787/api/runs/run_1/events');
    assert.equal(source.listeners['run.event'].length, 1);

    source.emit('run.event', {
      type: 'run.started',
      run_id: 'run_1',
      plan_id: 'plan_1',
      seq: 1,
      timestamp: '2026-06-19T00:00:00Z',
      payload: {},
    });
    source.emit('run.event', {
      type: terminalType,
      run_id: 'run_1',
      plan_id: 'plan_1',
      seq: 2,
      timestamp: '2026-06-19T00:00:01Z',
      payload: terminalType === 'run.completed' ? { status: 'completed' } : {},
    });

    assert.deepEqual(received, ['run.started', terminalType]);
    assert.equal(source.closeCount, 1);
  });
}

test('streamRunEvents keeps the stream open when run.completed means approval is required', () => {
  delete process.env.NEXT_PUBLIC_API_URL;
  FakeEventSource.instances = [];
  globalThis.EventSource = FakeEventSource as unknown as typeof EventSource;

  streamRunEvents('run_1');

  const source = FakeEventSource.instances[0];
  source.emit('run.event', {
    type: 'run.completed',
    run_id: 'run_1',
    plan_id: 'plan_1',
    seq: 1,
    timestamp: '2026-06-19T00:00:00Z',
    payload: { status: 'approval_required' },
  });

  assert.equal(source.closeCount, 0);
});
