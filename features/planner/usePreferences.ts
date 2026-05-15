// features/planner/usePreferences.ts
'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import type { UserPreferences } from '../../types/api';
import {
  getUserProfile,
  saveUserProfile,
  type BackendUserPreference,
  type BackendUserProfile,
} from './apiClient';

const DEFAULT_PREFERENCES: UserPreferences = {
  profile: { display_name: '用户', email: 'user@example.com' },
  diet: { fitness_friendly: true, vegetarian: false, gluten_free: false, allergies: [] },
  location: { radius_km: 5, favorite_places: [] },
  notifications: { execution_reminder: true, plan_change: true, weekly_digest: false },
};

const USER_ID = 'local_demo_user';

// --- Conversion: Backend UserProfile (key-value) <-> Frontend UserPreferences (structured) ---

function profileToPreferences(profile: BackendUserProfile): UserPreferences {
  const result: UserPreferences = JSON.parse(JSON.stringify(DEFAULT_PREFERENCES));
  for (const pref of [...profile.learned_preferences, ...profile.explicit_preferences, ...profile.session_preferences]) {
    const parts = pref.key.split('.');
    if (parts.length !== 2) continue;
    const [section, field] = parts as [string, string];
    if (section in result) {
      const sectionObj = result[section as keyof UserPreferences] as Record<string, unknown>;
      if (field in sectionObj) {
        sectionObj[field] = pref.value;
      }
    }
  }
  return result;
}

function preferencesToProfile(prefs: UserPreferences): BackendUserProfile {
  const flat: Record<string, unknown> = {};
  for (const [section, values] of Object.entries(prefs)) {
    if (typeof values === 'object' && values !== null) {
      for (const [field, value] of Object.entries(values as Record<string, unknown>)) {
        flat[`${section}.${field}`] = value;
      }
    }
  }
  const explicit_preferences: BackendUserPreference[] = Object.entries(flat).map(([key, value]) => ({
    key,
    value,
    source: 'explicit',
    confidence: 1.0,
    scope: 'user',
    evidence: '',
    expires_at: '',
    user_editable: true,
    sensitive: false,
  }));
  return {
    user_id: USER_ID,
    explicit_preferences,
    learned_preferences: [],
    session_preferences: [],
  };
}

export function usePreferences() {
  const [preferences, setPreferences] = useState<UserPreferences>(DEFAULT_PREFERENCES);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showSaved, setShowSaved] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    getUserProfile(USER_ID)
      .then((profile) => {
        setPreferences(profileToPreferences(profile));
      })
      .catch(() => {
        // backend unavailable, use defaults
      })
      .finally(() => setLoading(false));
  }, []);

  const update = useCallback(
    async (updater: (prev: UserPreferences) => UserPreferences) => {
      const updated = updater(preferences);
      setPreferences(updated);
      setSaving(true);
      try {
        await saveUserProfile(USER_ID, preferencesToProfile(updated));
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
