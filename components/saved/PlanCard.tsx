'use client';

import React, { useState } from 'react';
import { Calendar, MapPin, Edit3, Play, Trash2 } from 'lucide-react';
import { Badge } from '../ui/Badge';
import type { PlanSummary } from '../../types/api';
import styles from './PlanCard.module.css';

const STATUS_BADGE: Record<PlanSummary['status'], { variant: 'info' | 'success' | 'default' | 'warning'; label: string }> = {
  draft: { variant: 'default', label: '草稿' },
  saved: { variant: 'info', label: '已保存' },
  ready: { variant: 'info', label: '已生成' },
  pending_approval: { variant: 'warning', label: '待审批' },
  partially_completed: { variant: 'warning', label: '部分完成' },
  executing: { variant: 'warning', label: '执行中' },
  completed: { variant: 'success', label: '已完成' },
  cancelled: { variant: 'default', label: '已取消' },
  validation_failed: { variant: 'warning', label: '校验失败' },
};

export interface PlanCardProps {
  plan: PlanSummary;
  index: number;
  selected: boolean;
  onSelect: () => void;
  onEdit: () => void;
  onExecute: () => void;
  onDelete: () => void;
}

export function PlanCard({ plan, index, selected, onSelect, onEdit, onExecute, onDelete }: PlanCardProps) {
  const [removing, setRemoving] = useState(false);
  const status = STATUS_BADGE[plan.status];

  function handleDelete() {
    setRemoving(true);
    setTimeout(onDelete, 300);
  }

  return (
    <article
      className={`${styles.card} ${selected ? styles.selected : ''} ${removing ? styles.removing : ''}`}
      style={{ '--index': index } as React.CSSProperties}
      onClick={onSelect}
      data-testid={`plan-card-${plan.id}`}
    >
      <div className={styles.header}>
        <h3 className={styles.title}>{plan.title}</h3>
        <Badge variant={status.variant}>{status.label}</Badge>
      </div>
      <p className={styles.summary}>{plan.summary}</p>
      <div className={styles.meta}>
        {plan.location && (
          <span className={styles.metaItem}><MapPin size={12} /> {plan.location}</span>
        )}
        {plan.estimated_cost && (
          <span className={styles.metaItem}><Calendar size={12} /> {plan.estimated_cost}</span>
        )}
        <span className={styles.metaItem}>{plan.itinerary_count} 个行程</span>
      </div>
      <div className={styles.tags}>
        {plan.tags.map((tag) => (
          <span key={tag} className={styles.tag}>{tag}</span>
        ))}
      </div>
      <div className={styles.footer}>
        <button type="button" className={styles.editBtn} data-testid={`plan-edit-${plan.id}`} onClick={(e) => { e.stopPropagation(); onEdit(); }}>
          <Edit3 size={14} /> 编辑
        </button>
        <button type="button" className={styles.executeBtn} data-testid={`plan-execute-${plan.id}`} onClick={(e) => { e.stopPropagation(); onExecute(); }}>
          <Play size={14} /> 执行
        </button>
        <button type="button" className={styles.deleteBtn} onClick={(e) => { e.stopPropagation(); handleDelete(); }} data-testid={`plan-delete-${plan.id}`}>
          <Trash2 size={14} />
        </button>
      </div>
    </article>
  );
}
