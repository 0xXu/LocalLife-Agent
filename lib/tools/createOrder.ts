import { sideEffectTool } from './common';

export const createOrderTool = sideEffectTool('create_order', 'ORD', (input) => ({
  order_id: input.order_id ?? 'order_seed',
  items: input.items ?? [{ name: '低脂套餐', quantity: 1 }],
  pickup_time: input.pickup_time ?? input.time ?? '16:00',
}));
