import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { ActionLedgerPanel } from '../../components/plan/ActionLedgerPanel';

test('action ledger panel renders durable action ids, selected scope, and completed status', () => {
  const html = renderToStaticMarkup(
    <ActionLedgerPanel
      actions={[
        { action_id: 'act_msg_001', tool: 'messaging', type: 'send_plan_message', label: '发送计划', detail: '发送给同行人', status: 'pending', payload: {} },
        { action_id: 'act_cal_001', tool: 'calendar', type: 'create_calendar_event', label: '创建日历', detail: '写入日程', status: 'succeeded', payload: {} },
      ]}
      selectedActions={new Set(['act_msg_001'])}
      executing={false}
      onToggleAction={() => {}}
      onSelectAll={() => {}}
      onDeselectAll={() => {}}
      onApprove={() => {}}
      onReject={() => {}}
    />,
  );

  assert.match(html, /act_msg_001/);
  assert.match(html, /发送计划/);
  assert.match(html, /1 \/ 1/);
  assert.match(html, /已完成/);
});

test('action ledger panel presents ready plans without approval controls', () => {
  const html = renderToStaticMarkup(
    <ActionLedgerPanel
      actions={[]}
      selectedActions={new Set()}
      executing={false}
      phase="ready"
      onToggleAction={() => {}}
      onSelectAll={() => {}}
      onDeselectAll={() => {}}
      onApprove={() => {}}
      onReject={() => {}}
    />,
  );

  assert.match(html, /无需审批/);
  assert.doesNotMatch(html, /批准执行/);
  assert.doesNotMatch(html, /取消计划/);
});
