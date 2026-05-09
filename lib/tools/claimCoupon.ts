import { sideEffectTool } from './common';

export const claimCouponTool = sideEffectTool('claim_coupon', 'CPN', (input) => ({
  coupon_id: input.coupon_id ?? 'coupon_seed',
  rules: input.rules ?? '到店核销后生效；未核销订单支持退款。',
  price: input.price ?? 0,
}));
