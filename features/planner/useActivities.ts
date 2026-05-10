// features/planner/useActivities.ts
'use client';

import { useState, useEffect, useCallback } from 'react';
import type { ActivityRecord, ActivityStats } from '../../types/api';
import { fetchActivities } from './mockData';

export function useActivities() {
  const [activities, setActivities] = useState<ActivityRecord[]>([]);
  const [stats, setStats] = useState<ActivityStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchActivities();
      setActivities(data.activities);
      setStats(data.stats);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { activities, stats, loading, error, refetch: load };
}
