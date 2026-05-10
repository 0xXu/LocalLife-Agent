// features/planner/usePreferences.ts
'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import type { UserPreferences } from '../../types/api';
import { fetchPreferences, savePreferences } from './mockData';

const DEFAULT_PREFERENCES: UserPreferences = {
  profile: { display_name: '用户', email: 'user@example.com' },
  diet: { fitness_friendly: true, vegetarian: false, gluten_free: false, allergies: [] },
  location: { radius_km: 5, favorite_places: [] },
  notifications: { execution_reminder: true, plan_change: true, weekly_digest: false },
};

export function usePreferences() {
  const [preferences, setPreferences] = useState<UserPreferences>(DEFAULT_PREFERENCES);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showSaved, setShowSaved] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    fetchPreferences().then((p) => {
      setPreferences(p);
      setLoading(false);
    });
  }, []);

  const update = useCallback(
    async (updater: (prev: UserPreferences) => UserPreferences) => {
      const updated = updater(preferences);
      setPreferences(updated);
      setSaving(true);
      try {
        await savePreferences(updated);
        setShowSaved(true);
        clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => setShowSaved(false), 1500);
      } finally {
        setSaving(false);
      }
    },
    [preferences],
  );

  return { preferences, loading, saving, showSaved, update };
}
