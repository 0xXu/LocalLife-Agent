import React from 'react';
import { CalendarPlus, MessageSquareShare, ReceiptText, ShoppingBag, Ticket, Utensils } from 'lucide-react';

type BottomExecutionBarProps = {
  actions: Array<Record<string, any>>;
  onExecute?: () => void;
};

const actionLabels: Record<string, string> = {
  reserve_activity: '预约活动',
  create_reservation: '预订餐厅',
  claim_coupon: '领取团购券',
  create_order: '创建点单',
  send_plan_message: '发送计划',
  create_calendar_event: '创建日历',
};

const actionIcons: Record<string, typeof Ticket> = {
  reserve_activity: Ticket,
  create_reservation: Utensils,
  claim_coupon: ReceiptText,
  create_order: ShoppingBag,
  send_plan_message: MessageSquareShare,
  create_calendar_event: CalendarPlus,
};

export function BottomExecutionBar({ actions, onExecute }: BottomExecutionBarProps) {
  return (
    <section className="bottom-execution-bar" aria-label="确认执行">
      <div className="bottom-action-list">
        {actions.map((action) => {
          const tool = action.tool ?? action.type;
          const Icon = actionIcons[tool] ?? Ticket;
          return (
            <span key={`${tool}_${action.label}`}>
              <Icon size={16} />
              {actionLabels[tool] ?? action.label}
            </span>
          );
        })}
      </div>
      <button className="primary-button compact" type="button" onClick={onExecute}>确认执行</button>
    </section>
  );
}
