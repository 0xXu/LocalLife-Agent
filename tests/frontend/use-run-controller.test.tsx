import test from 'node:test';
import assert from 'node:assert/strict';
import React, { act, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import { JSDOM } from 'jsdom';

import { useRunController, type RunController } from '../../features/runs/useRunController';

type FetchCall = { url: string; init?: RequestInit };

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

test('useRunController starts a run and reduces named run.event frames', async () => {
  delete process.env.NEXT_PUBLIC_API_URL;
  FakeEventSource.instances = [];
  globalThis.EventSource = FakeEventSource as unknown as typeof EventSource;
  const calls = installFetch({
    run_id: 'run_1',
    plan_id: 'plan_1',
    status: 'queued',
    events_url: '/api/runs/run_1/events',
  });
  const { readController } = renderHook();

  await act(async () => {
    await readController().start('家庭半日计划');
  });

  assert.equal(calls[0].url, 'http://127.0.0.1:8787/api/runs');
  assert.equal(calls[0].init?.method, 'POST');
  assert.equal(calls[0].init?.body, JSON.stringify({ goal: '家庭半日计划', mode: 'plan' }));
  assert.equal(FakeEventSource.instances[0].url, 'http://127.0.0.1:8787/api/runs/run_1/events');
  assert.equal(FakeEventSource.instances[0].listeners['run.event'].length, 1);
  assert.equal(readController().state.runId, 'run_1');
  assert.equal(readController().state.planId, 'plan_1');

  await act(async () => {
    FakeEventSource.instances[0].emit('run.event', {
      type: 'approval.required',
      run_id: 'run_1',
      plan_id: 'plan_1',
      seq: 1,
      timestamp: '2026-06-19T00:00:00Z',
      payload: { actions: [{ action_id: 'act_1' }] },
    });
  });

  assert.equal(readController().state.status, 'approval_required');
  assert.deepEqual(readController().state.pendingActions, [{ action_id: 'act_1' }]);
});

test('useRunController approves and rejects by run id', async () => {
  delete process.env.NEXT_PUBLIC_API_URL;
  FakeEventSource.instances = [];
  globalThis.EventSource = FakeEventSource as unknown as typeof EventSource;
  const calls = installFetch({
    run_id: 'run_1',
    plan_id: 'plan_1',
    status: 'queued',
    events_url: '/api/runs/run_1/events',
  });
  const { readController } = renderHook();

  await act(async () => {
    await readController().start('家庭半日计划');
  });
  await act(async () => {
    await readController().approve(['act_1']);
  });
  await act(async () => {
    await readController().reject();
  });

  assert.deepEqual(calls.map((call) => [call.url, call.init?.method ?? 'GET']), [
    ['http://127.0.0.1:8787/api/runs', 'POST'],
    ['http://127.0.0.1:8787/api/runs/run_1/actions/approve', 'POST'],
    ['http://127.0.0.1:8787/api/runs/run_1/actions/reject', 'POST'],
  ]);
  assert.equal(calls[1].init?.body, JSON.stringify({ action_ids: ['act_1'] }));
  assert.equal(calls[2].init?.body, JSON.stringify({ reason: 'user_rejected' }));
});

function renderHook() {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
    url: 'http://127.0.0.1:4174/',
  });
  globalThis.window = dom.window as unknown as Window & typeof globalThis;
  globalThis.document = dom.window.document;
  Object.defineProperty(globalThis, 'navigator', {
    configurable: true,
    value: dom.window.navigator,
  });
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;

  let controller: RunController | null = null;

  function Harness() {
    const value = useRunController();
    useEffect(() => {
      controller = value;
    });
    return null;
  }

  const rootElement = dom.window.document.getElementById('root')!;
  const root = createRoot(rootElement);
  act(() => {
    root.render(<Harness />);
  });

  return {
    readController() {
      assert.ok(controller, 'controller not rendered');
      return controller;
    },
  };
}

function installFetch(body: Record<string, unknown>) {
  const calls: FetchCall[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return { ok: true, status: 200, statusText: 'OK', json: async () => body } as Response;
  }) as typeof fetch;
  return calls;
}
