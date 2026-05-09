import React from 'react';
import { CalendarPlus, MessageSquareShare, ReceiptText, ShoppingBag, Ticket, Utensils } from 'lucide-react';

type CommercialActionsProps = {
  actions: Array<Record<string, any>>;
};

const labels: Record<string, string> = {
  reserve_activity: '活动预约',
  create_reservation: '餐厅订座',
  claim_coupon: '团购券',
  create_order: '点单',
  send_plan_message: '发送计划',
  create_calendar_event: '日历',
};

const icons: Record<string, typeof Ticket> = {
  reserve_activity: Ticket,
  create_reservation: Utensils,
  claim_coupon: ReceiptText,
  create_order: ShoppingBag,
  send_plan_message: MessageSquareShare,
  create_calendar_event: CalendarPlus,
};

export function CommercialActions({ actions }: CommercialActionsProps) {
  return (
    <section className="commercial-actions">
      <h3>商业执行</h3>
      <div className="commercial-action-grid">
        {actions.map((action) => {
          const tool = action.tool ?? action.type;
          const Icon = icons[tool] ?? Ticket;
          return (
            <article key={`${tool}_${action.label}`}>
              <Icon size={17} />
              <strong>{labels[tool] ?? action.label}</strong>
              <span>{action.detail ?? action.target ?? '确认后执行'}</span>
            </article>
          );
        })}
      </div>
    </section>
  );
}
