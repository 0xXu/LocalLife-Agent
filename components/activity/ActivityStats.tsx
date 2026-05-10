'use client';

import React from 'react';
import { BarChart3, DollarSign, Utensils } from 'lucide-react';
import type { ActivityStats as StatsType } from '../../types/api';
import styles from './ActivityStats.module.css';

export interface ActivityStatsProps {
  stats: StatsType;
}

export function ActivityStats({ stats }: ActivityStatsProps) {
  return (
    <div className={styles.stats}>
      <div className={styles.card} style={{ '--index': 0 } as React.CSSProperties}>
        <div className={`${styles.icon} ${styles.iconBlue}`}><BarChart3 size={16} /></div>
        <div className={styles.label}>已执行计划</div>
        <div className={styles.value}>{stats.total_plans}</div>
      </div>
      <div className={styles.card} style={{ '--index': 1 } as React.CSSProperties}>
        <div className={`${styles.icon} ${styles.iconGreen}`}><DollarSign size={16} /></div>
        <div className={styles.label}>总支出</div>
        <div className={styles.value}>约 {stats.total_cost.toLocaleString()} 元</div>
      </div>
      <div className={styles.card} style={{ '--index': 2 } as React.CSSProperties}>
        <div className={`${styles.icon} ${styles.iconCoral}`}><Utensils size={16} /></div>
        <div className={styles.label}>高频类型</div>
        <div className={styles.value}>{stats.frequent_type}</div>
      </div>
    </div>
  );
}
