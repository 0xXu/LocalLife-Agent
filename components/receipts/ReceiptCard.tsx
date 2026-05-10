'use client';

import React from 'react';
import { CalendarPlus, Check, MessageSquareShare, ReceiptText, ShoppingBag, Ticket, Utensils, X } from 'lucide-react';

type ReceiptCardProps = {
  receipt: {
    type: string;
    tool: string;
    id: string;
    status: string;
    detail: string;
    payload?: Record<string, unknown>;
  };
  index: number;
};

const toolIcons: Record<string, typeof Ticket> = {
  reserve_activity: Ticket,
  create_reservation: Utensils,
  claim_coupon: ReceiptText,
  create_order: ShoppingBag,
  send_plan_message: MessageSquareShare,
  create_calendar_event: CalendarPlus,
};

const toolLabels: Record<string, string> = {
  reserve_activity: '活动预约',
  create_reservation: '餐厅订座',
  claim_coupon: '团购券',
  create_order: '点单',
  send_plan_message: '发送计划',
  create_calendar_event: '日历事件',
};

export function ReceiptCard({ receipt, index }: ReceiptCardProps) {
  const Icon = toolIcons[receipt.tool] ?? Ticket;
  const label = toolLabels[receipt.tool] ?? receipt.tool;
  const isSuccess = receipt.status === 'success' || receipt.status === 'ok';

  return (
    <div className="receipt-card" style={{ animationDelay: `${index * 100}ms` }}>
      <div className={`receipt-card-status ${isSuccess ? 'success' : 'failed'}`}>
        {isSuccess ? <Check size={16} /> : <X size={16} />}
      </div>
      <div className="receipt-card-icon"><Icon size={20} /></div>
      <div className="receipt-card-body">
        <strong>{label}</strong>
        <span className="receipt-card-id">{receipt.id}</span>
        <p>{receipt.detail}</p>
      </div>
    </div>
  );
}
