import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { TracePanel } from '../../components/trace/TracePanel';

test('trace panel renders readable steps and expandable tool IO', () => {
  const html = renderToStaticMarkup(
    <TracePanel
      trace={[
        { agent: 'IntentParserAgent', tool: 'parse_user_goal', status: 'ok', message: '正在理解你的约束', input_summary: { goal_length: 42 }, output_summary: { scenario: 'family' }, duration_ms: 140 },
      ]}
      toolCalls={[
        { tool: 'check_availability', input_summary: { place_id: 'r_014', time: '18:00', party_size: 3 }, output_summary: { available: true, slot: '18:10' }, status: 'ok', duration_ms: 90, side_effect: false },
      ]}
    />,
  );

  assert.match(html, /正在理解你的约束/);
  assert.match(html, /check_availability/);
  assert.match(html, /"place_id":"r_014"/);
  assert.match(html, /"available":true/);
});
