import React from 'react';

type ConfirmationDialogProps = {
  actions: Array<Record<string, any>>;
};

function toList(value: unknown): unknown[] {
  if (Array.isArray(value)) {
    return value;
  }
  if (value === undefined || value === null || value === '') {
    return [];
  }
  return [value];
}

function getLabel(value: unknown): string {
  if (typeof value === 'string' || typeof value === 'number') {
    return String(value);
  }
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    return String(record.name ?? record.title ?? record.label ?? record.id ?? '');
  }
  return '';
}

function joinLabels(value: unknown): string {
  return toList(value).map(getLabel).filter(Boolean).join('、');
}

function getPeople(payload: Record<string, any>, fallback = 3) {
  return payload.party_size ?? payload.people ?? payload.participants ?? fallback;
}

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
        <li>将为 {getPeople(activity, getPeople(reservation))} 人预订活动，时间 {activity.time ?? '待确认'}</li>
        <li>将为 {getPeople(reservation)} 人预订餐厅，手机号尾号 {reservation.phone_tail ?? '1234'}</li>
        <li>团购券价格 {coupon.price ?? 0}，退款规则：{coupon.rules ?? '未核销可退款'}</li>
        <li>点单项目：{joinLabels(order.items ?? order.item_names ?? order.dishes) || '待选择'}</li>
        <li>发送对象：{message.to ?? '待确认'}，内容会在发送前展示</li>
        <li>日历参与人：{joinLabels(calendar.participants ?? calendar.attendees) || '仅自己'}</li>
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
