import React from 'react';

type ConfirmationDialogProps = {
  actions: Array<Record<string, any>>;
};

export function ConfirmationDialog({ actions }: ConfirmationDialogProps) {
  const byTool = Object.fromEntries(actions.map((action) => [action.tool ?? action.type, action]));
  const reservation = byTool.create_reservation?.payload ?? {};
  const coupon = byTool.claim_coupon?.payload ?? {};
  const order = byTool.create_order?.payload ?? {};
  const message = byTool.send_plan_message?.payload ?? {};
  const calendar = byTool.create_calendar_event?.payload ?? {};
  const activity = byTool.reserve_activity?.payload ?? {};

  return (
    <section className="confirmation-dialog" role="dialog" aria-label="执行前确认">
      <h2>执行前确认</h2>
      <ul>
        <li>将为 {activity.party_size ?? reservation.party_size ?? 3} 人预订活动，时间 {activity.time ?? '待确认'}</li>
        <li>将为 {reservation.party_size ?? 3} 人预订餐厅，手机号尾号 {reservation.phone_tail ?? '1234'}</li>
        <li>团购券价格 {coupon.price ?? 0}，退款规则：{coupon.rules ?? '未核销可退款'}</li>
        <li>点单项目：{(order.items ?? []).map((item: Record<string, any>) => item.name).join('、') || '待选择'}</li>
        <li>发送对象：{message.to ?? '待确认'}，内容会在发送前展示</li>
        <li>日历参与人：{(calendar.participants ?? []).join('、') || '仅自己'}</li>
      </ul>
    </section>
  );
}

export function createConfirmationSnapshot(actions: Array<Record<string, any>>) {
  return {
    confirmed_at: new Date().toISOString(),
    visible_actions: actions,
    visible_message_content: actions.find((action) => action.tool === 'send_plan_message')?.payload?.content ?? '',
    visible_coupon_rules: actions.filter((action) => action.tool === 'claim_coupon').map((action) => action.payload?.rules ?? ''),
    visible_order_items: actions.find((action) => action.tool === 'create_order')?.payload?.items ?? [],
    phone_tail: actions.find((action) => action.tool === 'create_reservation')?.payload?.phone_tail ?? '',
  };
}
