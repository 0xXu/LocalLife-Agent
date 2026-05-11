// features/planner/usePlans.ts
'use client';

import { useState, useEffect, useCallback } from 'react';
import type { PlanSummary } from '../../types/api';
import type { PlanResponse } from '../../types/weekendpilot';
import { confirmPlan, executePlan, listPlans } from './apiClient';

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

  const execute = useCallback(async (planId: string) => {
    setPlans((prev) => prev.map((p) => (p.id === planId ? { ...p, status: 'executing' } : p)));
    await confirmPlan(planId);
    const result = await executePlan(planId);
    const summary = summaryFromPlanResponse(result);
    setPlans((prev) => prev.map((p) => (p.id === planId ? summary : p)));
    return summary;
  }, []);

  return { plans, loading, error, refetch: load, update, remove, execute };
}

function summaryFromPlanResponse(result: PlanResponse): PlanSummary {
  const plan = result.plan as any;
  return {
    id: plan.id,
    title: plan.title,
    status: plan.status === 'completed' ? 'completed' : 'saved',
    summary: plan.summary,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    tags: [
      result.constraints?.scenario === 'family' ? '家庭' :
        result.constraints?.scenario === 'friends' ? '朋友' :
          result.constraints?.scenario === 'date' ? '约会' :
            result.constraints?.scenario === 'rainy_indoor' ? '雨天' : '本地生活',
      ...((result.constraints?.preferences?.activity ?? []) as string[]).slice(0, 2),
    ],
    location: result.constraints?.constraints?.radius_km ? `${result.constraints.constraints.radius_km} 公里内` : undefined,
    estimated_cost: plan.overview?.estimatedCost,
    itinerary_count: plan.itinerary?.length ?? 0,
  };
}
