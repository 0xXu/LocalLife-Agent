'use client';

import React from 'react';
import { X, MapPin, Calendar, DollarSign, ListChecks } from 'lucide-react';
import { Badge } from '../ui/Badge';
import type { PlanSummary } from '../../types/api';
import styles from './PlanDetailPanel.module.css';

const STATUS_MAP: Record<PlanSummary['status'], { variant: 'info' | 'success' | 'default' | 'warning'; label: string }> = {
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

export interface PlanDetailPanelProps {
  plan: PlanSummary;
  onClose: () => void;
}

export function PlanDetailPanel({ plan, onClose }: PlanDetailPanelProps) {
  const status = STATUS_MAP[plan.status];
  const created = new Date(plan.created_at).toLocaleDateString('zh-CN', {
    year: 'numeric', month: 'long', day: 'numeric',
  });
  return (
    <>
      <div className={styles.overlay} onClick={onClose} />
      <aside className={styles.panel} data-testid="plan-detail-panel">
        <div className={styles.handle} />
        <div className={styles.header}>
          <h2>{plan.title}</h2>
          <button type="button" className={styles.closeBtn} data-testid="details-close" onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </div>
        <div className={styles.section}>
          <Badge variant={status.variant} size="md">{status.label}</Badge>
        </div>
        <div className={styles.section}>
          <div className={styles.sectionLabel}>方案摘要</div>
          <p className={styles.sectionValue}>{plan.summary}</p>
        </div>
        <div className={styles.detailGrid}>
          <div className={styles.detailItem}>
            <span className={styles.detailLabel}><MapPin size={12} /> 地点</span>
            <span className={styles.detailValue}>{plan.location ?? '未指定'}</span>
          </div>
          <div className={styles.detailItem}>
            <span className={styles.detailLabel}><DollarSign size={12} /> 预算</span>
            <span className={styles.detailValue}>{plan.estimated_cost ?? '未指定'}</span>
          </div>
          <div className={styles.detailItem}>
            <span className={styles.detailLabel}><ListChecks size={12} /> 行程数</span>
            <span className={styles.detailValue}>{plan.itinerary_count} 个</span>
          </div>
          <div className={styles.detailItem}>
            <span className={styles.detailLabel}><Calendar size={12} /> 创建时间</span>
            <span className={styles.detailValue}>{created}</span>
          </div>
        </div>
        <div className={styles.section}>
          <div className={styles.sectionLabel}>标签</div>
          <div className={styles.tags}>
            {plan.tags.map((tag) => (<span key={tag} className={styles.tag}>{tag}</span>))}
          </div>
        </div>
      </aside>
    </>
  );
}
