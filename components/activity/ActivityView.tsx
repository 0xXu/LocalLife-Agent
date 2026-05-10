'use client';

import React, { useState, useMemo } from 'react';
import { AlertCircle, ReceiptText } from 'lucide-react';
import { SearchInput } from '../ui/SearchInput';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';
import { useActivities } from '../../features/planner/useActivities';
import { ActivityStats } from './ActivityStats';
import { ActivityItem } from './ActivityItem';
import styles from './ActivityView.module.css';

type Filter = 'all' | 'completed' | 'failed';

const FILTER_OPTIONS: { value: Filter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
];

export function ActivityView() {
  const { activities, stats, loading, error, refetch } = useActivities();
  const [filter, setFilter] = useState<Filter>('all');
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    let result = activities;
    if (filter !== 'all') result = result.filter((a) => a.status === filter);
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter((a) =>
        a.plan_title.toLowerCase().includes(q) ||
        a.summary.toLowerCase().includes(q) ||
        a.receipts.some((r) => r.detail.toLowerCase().includes(q)),
      );
    }
    return result;
  }, [activities, filter, search]);

  if (loading) {
    return (
      <section className={styles.view}>
        <h1 className={styles.title}>执行记录</h1>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16 }}>
          {Array.from({ length: 3 }).map((_, i) => (<Skeleton key={i} variant="rectangular" height={80} />))}
        </div>
        {Array.from({ length: 4 }).map((_, i) => (<Skeleton key={i} variant="rectangular" height={100} style={{ marginBottom: 8 }} />))}
      </section>
    );
  }

  return (
    <section className={styles.view}>
      <div className={styles.header}>
        <h1 className={styles.title}>执行记录</h1>
        <div className={styles.controls}>
          <SearchInput value={search} onChange={setSearch} placeholder="搜索记录..." />
        </div>
      </div>

      {error && (
        <div className={styles.error}>
          <AlertCircle size={16} />{error}
          <button type="button" className={styles.retryBtn} onClick={refetch}>重试</button>
        </div>
      )}

      {stats && <ActivityStats stats={stats} />}

      <div className={styles.filterChips}>
        {FILTER_OPTIONS.map((opt) => (
          <button key={opt.value} type="button"
            className={`${styles.chip} ${filter === opt.value ? styles.chipActive : ''}`}
            onClick={() => setFilter(opt.value)}>
            {opt.label}
          </button>
        ))}
      </div>

      {filtered.length === 0 && !error ? (
        <EmptyState
          icon={<ReceiptText size={28} />}
          title="还没有执行记录"
          description="执行你的第一个计划后，记录会显示在这里"
        />
      ) : (
        <div className={styles.content}>
          <div className={styles.timeline}>
            {filtered.map((activity, i) => (
              <ActivityItem key={activity.id} activity={activity} index={i} isLast={i === filtered.length - 1} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
