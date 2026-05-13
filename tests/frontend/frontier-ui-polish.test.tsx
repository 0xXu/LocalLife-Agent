import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { ChatView } from '../../components/chat/ChatView';
import { ConfirmView } from '../../components/confirm/ConfirmView';
import { PlanningProgress } from '../../components/planning/PlanningProgress';
import type { PlanResponse } from '../../types/weekendpilot';

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

test('confirmation screen summarizes selected execution scope', () => {
  const result = makePlanResponse();
  const html = renderToStaticMarkup(
    <ConfirmView
      result={result}
      selectedActions={new Set(['send_plan_message_group'])}
      onToggleAction={() => {}}
      onSelectAll={() => {}}
      onDeselectAll={() => {}}
      onExecute={() => {}}
      onBack={() => {}}
      executing={false}
    />,
  );

  assert.match(html, /即将执行 1 \/ 2 项/);
  assert.match(html, /仅执行已勾选的动作/);
});

function makePlanResponse(): PlanResponse {
  return {
    constraints: {},
    trace: [],
    tool_calls: [],
    progress: [],
    pending_actions: [],
    actions: [],
    variants: [],
    receipts: [],
    plan: {
      id: 'plan_frontier_ui',
      status: 'pending_confirmation',
      title: '安静散步咖啡计划',
      summary: '轻量本地生活计划',
      itinerary: [],
      actions: [
        {
          id: 'send_plan_message_group',
          type: 'message',
          tool: 'send_plan_message',
          label: '发送计划',
          target: '同行人',
          detail: '发送计划摘要',
          requires_confirmation: true,
          payload: {},
        },
        {
          id: 'create_calendar_event_self',
          type: 'calendar',
          tool: 'create_calendar_event',
          label: '创建日历',
          target: '个人日历',
          detail: '写入 15:00-17:00',
          requires_confirmation: true,
          payload: {},
        },
      ],
      overview: {},
      constraint_fit: {},
      receipts: [],
      badges: [],
    },
  } as PlanResponse;
}
