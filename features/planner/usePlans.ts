// features/planner/usePlans.ts
'use client';

import { useState, useEffect, useCallback } from 'react';
import type { PlanSummary } from '../../types/api';
import { listPlans } from '../plans/api';

export function usePlans() {
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listPlans();
      setPlans(data.plans);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const update = useCallback(
    async (planId: string, updates: Partial<PlanSummary>) => {
      const current = plans.find((p) => p.id === planId);
      if (!current) throw new Error('Plan not found');
      const updated = { ...current, ...updates, updated_at: new Date().toISOString() };
      setPlans((prev) => prev.map((p) => (p.id === planId ? updated : p)));
      return updated;
    },
    [plans],
  );

  const remove = useCallback(async (planId: string) => {
    setPlans((prev) => prev.filter((p) => p.id !== planId));
  }, []);

  return { plans, loading, error, refetch: load, update, remove };
}
