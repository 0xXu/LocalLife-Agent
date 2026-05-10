'use client';

import React from 'react';
import { CalendarPlus, MessageSquareShare, ReceiptText, ShoppingBag, Ticket, Utensils } from 'lucide-react';

type ActionToggleProps = {
  action: Record<string, any>;
  selected: boolean;
  onToggle: () => void;
};

const actionLabels: Record<string, string> = {
  reserve_activity: '预约活动',
  create_reservation: '餐厅订座',
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

export function ActionToggle({ action, selected, onToggle }: ActionToggleProps) {
  const tool = action.tool ?? action.type;
  const Icon = actionIcons[tool] ?? Ticket;
  const label = actionLabels[tool] ?? action.label ?? tool;

  return (
    <button
      className={`action-toggle${selected ? ' active' : ''}`}
      type="button"
      onClick={onToggle}
      aria-pressed={selected}
    >
      <div className="action-toggle-icon"><Icon size={20} /></div>
      <div className="action-toggle-text">
        <strong>{label}</strong>
        <span>{action.detail ?? action.target ?? '确认后执行'}</span>
      </div>
      <div className="action-toggle-switch">
        <div className="action-toggle-track">
          <div className="action-toggle-thumb" />
        </div>
      </div>
    </button>
  );
}
