import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { ClarificationView } from '../../components/clarification/ClarificationView';

test('clarification view renders backend questions without a fake plan', () => {
  const html = renderToStaticMarkup(
    <ClarificationView
      goal="周末安排一下"
      clarification={{
        status: 'needs_clarification',
        plan_id: 'plan_clarify_001',
        missing_fields: ['time_window', 'activity_intent'],
        clarifying_questions: [
          { field: 'time_window', question: '你想安排今天、周六还是周日？大概几小时？' },
          { field: 'activity_intent', question: '你更想户外走走、室内放松、吃饭聚会，还是亲子活动？' },
        ],
        trace: [],
        tool_calls: [],
      }}
      onSubmitGoal={() => {}}
    />,
  );

  assert.match(html, /再补两点/);
  assert.match(html, /今天下午 2 小时/);
  assert.match(html, /继续生成/);
  assert.doesNotMatch(html, /确认方案/);
});
