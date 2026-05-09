import test from 'node:test';
import assert from 'node:assert/strict';

import { executeAllConfirmedActions, toolRegistry } from '../../lib/tools/toolRegistry';

test('tool registry exposes all fifteen detailed design tools with side effect metadata', () => {
  const tools = toolRegistry.schemas();
  assert.deepEqual(tools.map((tool) => tool.name), [
    'parse_user_goal',
    'get_weather',
    'search_places',
    'search_restaurants',
    'check_availability',
    'optimize_route',
    'build_itinerary',
    'validate_plan',
    'compare_alternatives',
    'reserve_activity',
    'create_reservation',
    'claim_coupon',
    'create_order',
    'send_plan_message',
    'create_calendar_event',
  ]);
  assert.deepEqual(
    tools.filter((tool) => tool.side_effect).map((tool) => tool.name),
    ['reserve_activity', 'create_reservation', 'claim_coupon', 'create_order', 'send_plan_message', 'create_calendar_event'],
  );
});

test('side-effect tools return realistic typed receipt payloads', async () => {
  const receipts = await executeAllConfirmedActions(makeSixActionFixture(), { confirmed: true, idempotencyKey: 'idem_001', humanConfirmationSnapshot: { visible_actions: 6 } });
  assert.deepEqual(receipts.map((receipt) => receipt.id.slice(0, 3)), ['TKT', 'RES', 'CPN', 'ORD', 'MSG', 'CAL']);
  assert.ok(receipts.find((receipt) => receipt.tool === 'claim_coupon')?.payload.rules.includes('退款'));
  assert.ok(receipts.find((receipt) => receipt.tool === 'create_order')?.payload.items.length >= 1);
});

function makeSixActionFixture() {
  return [
    { tool: 'reserve_activity', type: 'activity_reservation', label: '预约活动', payload: { place_id: 'a_001', party_size: 3, time: '14:00' } },
    { tool: 'create_reservation', type: 'restaurant_reservation', label: '预订餐厅', payload: { place_id: 'r_014', party_size: 3, time: '16:00' } },
    { tool: 'claim_coupon', type: 'coupon', label: '领取团购券', payload: { place_id: 'r_014', coupon_id: 'coupon_001' } },
    { tool: 'create_order', type: 'order', label: '创建点单', payload: { place_id: 'r_014', items: [{ name: '低脂套餐', quantity: 3 }] } },
    { tool: 'send_plan_message', type: 'message', label: '发送计划', payload: { to: 'family', content: '计划摘要' } },
    { tool: 'create_calendar_event', type: 'calendar', label: '创建日历', payload: { title: '家庭半日计划', participants: ['family'] } },
  ];
}
