import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { ConfirmationDialog } from '../../components/planner/ConfirmationDialog';

test('confirmation dialog shows concrete sensitive action details before execution', () => {
  const html = renderToStaticMarkup(<ConfirmationDialog actions={makeSixActionFixture()} />);
  assert.match(html, /将为 3 人预订/);
  assert.match(html, /手机号尾号/);
  assert.match(html, /团购券价格/);
  assert.match(html, /退款规则/);
  assert.match(html, /发送对象/);
  assert.match(html, /日历参与人/);
});

function makeSixActionFixture() {
  return [
    { tool: 'reserve_activity', label: '预约活动', payload: { party_size: 3, time: '14:00' } },
    { tool: 'create_reservation', label: '预订餐厅', payload: { party_size: 3, phone_tail: '1234' } },
    { tool: 'claim_coupon', label: '领取团购券', payload: { price: 1980, rules: '未核销可退款' } },
    { tool: 'create_order', label: '创建点单', payload: { items: [{ name: '低脂套餐' }] } },
    { tool: 'send_plan_message', label: '发送计划', payload: { to: '家庭群聊', content: '计划摘要' } },
    { tool: 'create_calendar_event', label: '创建日历', payload: { participants: ['老婆'] } },
  ];
}
