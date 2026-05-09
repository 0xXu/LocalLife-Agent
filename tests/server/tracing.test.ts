import test from 'node:test';
import assert from 'node:assert/strict';

import { normalizeTraceEvents } from '../../lib/observability/tracing';

test('normalizeTraceEvents merges graph spans, OpenAI agent spans, tool calls, retries, failures, and side effects', () => {
  const events = normalizeTraceEvents({
    trace: [
      { agent: 'Graph', tool: 'parse_user_goal', status: 'ok', message: '解析约束', duration_ms: 100 },
      { agent: 'OpenAI Agent', name: 'Intent Parser', status: 'succeeded', summary: '结构化输出', output_summary: { scenario: 'family' } },
      { agent: 'Executor', tool: 'create_reservation', status: 'retrying', message: '第一次超时', error: { code: 'timeout' }, side_effect_id: 'idem_001' },
      { agent: 'Executor', tool: 'create_reservation', status: 'failed', message: '重试失败', error: 'provider_timeout' },
    ],
    tool_calls: [
      { tool: 'send_plan_message', input_summary: { channel: 'family' }, output_summary: { id: 'msg_001' }, status: 'ok', side_effect: true },
    ],
  });

  assert.deepEqual(events.map((event) => event.kind), ['trace', 'trace', 'trace', 'trace', 'tool_call']);
  assert.equal(events[1].agent, 'OpenAI Agent');
  assert.equal(events[2].status, 'retrying');
  assert.equal(events[2].side_effect_id, 'idem_001');
  assert.equal(events[3].error_json, '"provider_timeout"');
  assert.equal(events[4].side_effect, true);
});
