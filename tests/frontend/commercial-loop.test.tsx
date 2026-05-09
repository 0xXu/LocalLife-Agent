import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { CommercialActions } from '../../components/planner/CommercialActions';
import { ReceiptStack } from '../../components/planner/ReceiptStack';

test('commercial action UI shows reservation, activity, coupon, order, message, and calendar', () => {
  const html = renderToStaticMarkup(<CommercialActions actions={makeSixActionFixture()} />);
  for (const label of ['活动预约', '餐厅订座', '团购券', '点单', '发送计划', '日历']) {
    assert.match(html, new RegExp(label));
  }
});

test('receipt stack renders all machine-verifiable receipt ids', () => {
  const html = renderToStaticMarkup(<ReceiptStack receipts={makeSixReceiptFixture()} />);
  for (const prefix of ['TKT-', 'RES-', 'CPN-', 'ORD-', 'MSG-', 'CAL-']) {
    assert.match(html, new RegExp(prefix));
  }
});

function makeSixActionFixture() {
  return [
    { tool: 'reserve_activity', label: '预约活动', payload: {} },
    { tool: 'create_reservation', label: '预订餐厅', payload: {} },
    { tool: 'claim_coupon', label: '领取团购券', payload: {} },
    { tool: 'create_order', label: '创建点单', payload: {} },
    { tool: 'send_plan_message', label: '发送计划', payload: {} },
    { tool: 'create_calendar_event', label: '创建日历', payload: {} },
  ];
}

function makeSixReceiptFixture() {
  return [
    { id: 'TKT-1001', tool: 'reserve_activity', status: 'confirmed', detail: '活动预约完成', payload: { ticket_id: 'TKT-1001' } },
    { id: 'RES-1002', tool: 'create_reservation', status: 'confirmed', detail: '餐厅订座完成', payload: { reservation_id: 'RES-1002' } },
    { id: 'CPN-1003', tool: 'claim_coupon', status: 'confirmed', detail: '团购券领取完成', payload: { coupon_id: 'CPN-1003' } },
    { id: 'ORD-1004', tool: 'create_order', status: 'confirmed', detail: '点单完成', payload: { order_id: 'ORD-1004' } },
    { id: 'MSG-1005', tool: 'send_plan_message', status: 'confirmed', detail: '消息已发送', payload: { message_id: 'MSG-1005' } },
    { id: 'CAL-1006', tool: 'create_calendar_event', status: 'confirmed', detail: '日历已创建', payload: { event_id: 'CAL-1006' } },
  ];
}
