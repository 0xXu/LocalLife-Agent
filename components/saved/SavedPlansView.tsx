'use client';

import React, { useState } from 'react';
import { Grid2X2, List, AlertCircle } from 'lucide-react';
import { SegmentedControl } from '../ui/SegmentedControl';
import { SearchInput } from '../ui/SearchInput';
import { Skeleton } from '../ui/Skeleton';
import { usePlans } from '../../features/planner/usePlans';
import { PlanCard } from './PlanCard';
import { PlanDetailPanel } from './PlanDetailPanel';
import { PlanEditModal } from './PlanEditModal';
import { EmptyPlans } from './EmptyPlans';
import type { PlanSummary } from '../../types/api';
import styles from './SavedPlansView.module.css';

const VIEW_OPTIONS = [
  { value: 'grid' as const, label: '网格', icon: <Grid2X2 size={15} /> },
  { value: 'list' as const, label: '列表', icon: <List size={15} /> },
];

export interface SavedPlansViewProps {
  onNavigateHome?: () => void;
}

export function SavedPlansView({ onNavigateHome }: SavedPlansViewProps) {
  const { plans, loading, error, refetch, update, remove, execute } = usePlans();
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editingPlan, setEditingPlan] = useState<PlanSummary | null>(null);
  const [search, setSearch] = useState('');

  const filtered = plans.filter((p) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return p.title.toLowerCase().includes(q) || p.summary.toLowerCase().includes(q) || p.tags.some((t) => t.toLowerCase().includes(q));
  });

  const selected = plans.find((p) => p.id === selectedId) ?? null;

  const handleExecute = async (plan: PlanSummary) => {
    setSelectedId(plan.id);
    await execute(plan.id);
  };

  if (loading) {
    return (
      <section className={styles.view}>
        <div className={styles.header}>
          <div><h1 className={styles.title}>我的计划</h1><p className={styles.subtitle}>管理并执行你收藏的周末行程</p></div>
        </div>
        <div className={styles.grid}>
          {Array.from({ length: 3 }).map((_, i) => (<Skeleton key={i} variant="rectangular" height={180} />))}
        </div>
      </section>
    );
  }

  return (
    <section className={styles.view}>
      <div className={styles.header}>
        <div><h1 className={styles.title}>我的计划</h1><p className={styles.subtitle}>管理并执行你收藏的周末行程</p></div>
        <div className={styles.controls}>
          <SearchInput value={search} onChange={setSearch} placeholder="搜索计划..." inputTestId="saved-search-input" />
          <SegmentedControl options={VIEW_OPTIONS} value={viewMode} onChange={setViewMode} testIdPrefix="saved-view" />
        </div>
      </div>

      {error && (
        <div className={styles.error}>
          <AlertCircle size={16} />{error}
          <button type="button" className={styles.retryBtn} onClick={refetch}>重试</button>
        </div>
      )}

      {filtered.length === 0 && !error ? (
        <EmptyPlans onNavigateHome={onNavigateHome ?? (() => {})} />
      ) : (
        <div className={styles.content}>
          <div className={`${styles.grid} ${viewMode === 'list' ? styles.list : styles.gridMode}`} data-testid="saved-plans-list">
            {filtered.map((plan, i) => (
              <PlanCard key={plan.id} plan={plan} index={i} selected={plan.id === selectedId}
                onSelect={() => setSelectedId(plan.id)} onEdit={() => setEditingPlan(plan)}
                onExecute={() => { void handleExecute(plan); }} onDelete={() => remove(plan.id)} />
            ))}
          </div>
          {selected && <PlanDetailPanel plan={selected} onClose={() => setSelectedId(null)} />}
        </div>
      )}

      {editingPlan && (
        <PlanEditModal plan={editingPlan} onSave={async (updates) => { await update(editingPlan.id, updates); }} onClose={() => setEditingPlan(null)} />
      )}
    </section>
  );
}
