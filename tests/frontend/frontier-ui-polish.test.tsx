import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { ChatView } from '../../components/chat/ChatView';
import { ActionLedgerPanel } from '../../components/plan/ActionLedgerPanel';
import { PlanningProgress } from '../../components/planning/PlanningProgress';

test('chat entry explains open-domain planning quality signals', () => {
  const html = renderToStaticMarkup(
    <ChatView onSubmitGoal={() => {}} isPlanning={false} error={null} />,
  );

  assert.match(html, /开放域规划/);
  assert.match(html, /偏好记忆/);
  assert.match(html, /可解释候选/);
});

test('planning progress surfaces streaming backend reasoning text', () => {
  const html = renderToStaticMarkup(
    <PlanningProgress
      goal="想找一个能散步、能喝咖啡、不要太吵的地方"
      progress={['已识别安静、可散步、预算适中']}
      currentStep={1}
      streamingText="正在拉取候选并验证营业时间..."
    />,
  );

  assert.match(html, /正在拉取候选并验证营业时间/);
  assert.match(html, /2 \/ 6/);
});

test('action ledger summarizes selected execution scope', () => {
  const html = renderToStaticMarkup(
    <ActionLedgerPanel
      actions={[
        { action_id: 'act_msg_001', type: 'send_plan_message', tool: 'messaging', label: '发送计划', detail: '发送计划摘要', status: 'pending', payload: {} },
        { action_id: 'act_cal_001', type: 'create_calendar_event', tool: 'calendar', label: '创建日历', detail: '写入 15:00-17:00', status: 'pending', payload: {} },
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

  assert.match(html, /1 \/ 2/);
  assert.match(html, /执行账本/);
});
