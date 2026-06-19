import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { ReceiptsView } from '../../components/receipts/ReceiptsView';

test('receipts view counts backend succeeded receipts and renders stable ids', () => {
  const html = renderToStaticMarkup(
    <ReceiptsView
      receipts={[
        { receipt_id: 'rcpt_001', action_id: 'act_001', type: 'restaurant_reservation', tool: 'create_reservation', status: 'succeeded', detail: 'create_reservation completed', payload: {} },
        { receipt_id: 'rcpt_002', action_id: 'act_002', type: 'coupon', tool: 'claim_coupon', status: 'succeeded', detail: 'claim_coupon completed', payload: {} },
      ] as any}
      onNewPlan={() => {}}
    />,
  );

  assert.match(html, /成功 2 \/ 2 项操作/);
  assert.match(html, /rcpt_001/);
});

test('receipts view counts confirmed runtime receipts as successful', () => {
  const html = renderToStaticMarkup(
    <ReceiptsView
      receipts={[
        { id: 'receipt_1', action_id: 'act_send_plan_summary', type: 'send_plan_message', tool: 'messaging', status: 'confirmed', detail: 'message confirmed', payload: {} },
      ] as any}
      onNewPlan={() => {}}
    />,
  );

  assert.match(html, /成功 1 \/ 1 项操作/);
});
