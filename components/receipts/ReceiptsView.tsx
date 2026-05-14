'use client';

import React from 'react';
import { PartyPopper } from 'lucide-react';
import { ReceiptCard } from './ReceiptCard';

type ReceiptsViewProps = {
  receipts: Array<{
    type: string;
    tool: string;
    id?: string;
    receipt_id?: string;
    action_id?: string;
    status: string;
    detail: string;
    payload?: Record<string, unknown>;
  }>;
  onNewPlan: () => void;
};

export function ReceiptsView({ receipts, onNewPlan }: ReceiptsViewProps) {
  const successCount = receipts.filter((r) => ['success', 'ok', 'succeeded'].includes(r.status)).length;

  return (
    <section className="receipts-view">
      <div className="receipts-celebration">
        <div className="receipts-celebration-icon"><PartyPopper size={32} /></div>
        <h2>执行完成</h2>
        <p>成功 {successCount} / {receipts.length} 项操作</p>
      </div>
      <div className="receipts-list">
        {receipts.map((receipt, index) => (
          <ReceiptCard key={receipt.receipt_id ?? receipt.id ?? receipt.action_id ?? index} receipt={receipt} index={index} />
        ))}
      </div>
      <button className="primary-button" type="button" onClick={onNewPlan}>再来一局</button>
    </section>
  );
}
