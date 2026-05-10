'use client';

import React, { useState } from 'react';
import { CheckCircle2, ReceiptText, ChevronDown, ChevronUp } from 'lucide-react';
import type { ActivityRecord } from '../../types/api';
import styles from './ActivityItem.module.css';

export interface ActivityItemProps {
  activity: ActivityRecord;
  index: number;
  isLast: boolean;
}

export function ActivityItem({ activity, index, isLast }: ActivityItemProps) {
  const [showReceipts, setShowReceipts] = useState(false);
  const date = new Date(activity.executed_at).toLocaleDateString('zh-CN', {
    month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });

  return (
    <div className={styles.item} style={{ '--index': index } as React.CSSProperties}>
      <div className={styles.timeline}>
        <div className={`${styles.dot} ${index === 0 ? styles.dotActive : ''}`} />
        {!isLast && <div className={styles.line} />}
      </div>
      <div className={styles.body}>
        <div className={styles.meta}>
          <span>{date}</span>
          <span className={`${styles.statusBadge} ${activity.status === 'completed' ? styles.statusCompleted : styles.statusFailed}`}>
            {activity.status === 'completed' ? '已完成' : '失败'}
          </span>
        </div>
        <h3 className={styles.title}>{activity.plan_title}</h3>
        <p className={styles.summary}>{activity.summary}</p>
        {activity.total_cost && (
          <div className={styles.cost}><ReceiptText size={14} /> {activity.total_cost}</div>
        )}
        {activity.receipts.length > 0 && (
          <>
            <button type="button" className={styles.receiptToggle} data-testid={`activity-receipt-${index}`} onClick={() => setShowReceipts(!showReceipts)}>
              <ReceiptText size={14} />
              {showReceipts ? '收起回执' : `查看回执（${activity.receipts.length}）`}
              {showReceipts ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
            {showReceipts && (
              <div className={styles.receipts} data-testid="activity-receipt-panel">
                {activity.receipts.map((r) => (
                  <div key={r.id} className={styles.receiptItem}>
                    <CheckCircle2 size={14} className={styles.receiptIcon} />
                    {r.detail}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
