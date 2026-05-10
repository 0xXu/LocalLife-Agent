'use client';

import React, { useCallback } from 'react';
import { CheckCircle2, User, Utensils, MapPin, Bell } from 'lucide-react';
import { SegmentedControl } from '../ui/SegmentedControl';
import { Skeleton } from '../ui/Skeleton';
import { usePreferences } from '../../features/planner/usePreferences';
import { ProfileSection } from './ProfileSection';
import { DietSection } from './DietSection';
import { LocationSection } from './LocationSection';
import { NotificationSection } from './NotificationSection';
import styles from './SettingsView.module.css';

type SettingsTab = 'profile' | 'diet' | 'location' | 'notifications';

const TAB_OPTIONS = [
  { value: 'profile' as const, label: '用户资料', icon: <User size={15} /> },
  { value: 'diet' as const, label: '饮食偏好', icon: <Utensils size={15} /> },
  { value: 'location' as const, label: '位置偏好', icon: <MapPin size={15} /> },
  { value: 'notifications' as const, label: '通知', icon: <Bell size={15} /> },
];

export function SettingsView() {
  const { preferences, loading, showSaved, update } = usePreferences();
  const [activeTab, setActiveTab] = React.useState<SettingsTab>('profile');

  const handleProfileChange = useCallback(
    (field: 'display_name' | 'email', value: string) => {
      update((prev) => ({ ...prev, profile: { ...prev.profile, [field]: value } }));
    },
    [update],
  );

  const handleDietToggle = useCallback(
    (key: 'fitness_friendly' | 'vegetarian' | 'gluten_free') => {
      update((prev) => ({ ...prev, diet: { ...prev.diet, [key]: !prev.diet[key] } }));
    },
    [update],
  );

  const handleLocationChange = useCallback(
    (radius: number) => {
      update((prev) => ({ ...prev, location: { ...prev.location, radius_km: radius } }));
    },
    [update],
  );

  const handleNotifToggle = useCallback(
    (key: 'execution_reminder' | 'plan_change' | 'weekly_digest') => {
      update((prev) => ({ ...prev, notifications: { ...prev.notifications, [key]: !prev.notifications[key] } }));
    },
    [update],
  );

  if (loading) {
    return (
      <section className={styles.view}>
        <h1 className={styles.title}>设置</h1>
        <Skeleton variant="rectangular" height={40} style={{ marginBottom: 16 }} />
        <Skeleton variant="rectangular" height={200} />
      </section>
    );
  }

  return (
    <section className={styles.view}>
      <h1 className={styles.title}>设置</h1>
      <SegmentedControl options={TAB_OPTIONS} value={activeTab} onChange={setActiveTab} />
      <div className={styles.layout}>
        {activeTab === 'profile' && (
          <ProfileSection displayName={preferences.profile.display_name}
            email={preferences.profile.email} onChange={handleProfileChange} />
        )}
        {activeTab === 'diet' && (
          <DietSection fitnessFriendly={preferences.diet.fitness_friendly}
            vegetarian={preferences.diet.vegetarian} glutenFree={preferences.diet.gluten_free}
            onToggle={handleDietToggle} />
        )}
        {activeTab === 'location' && (
          <LocationSection radiusKm={preferences.location.radius_km} onChange={handleLocationChange} />
        )}
        {activeTab === 'notifications' && (
          <NotificationSection executionReminder={preferences.notifications.execution_reminder}
            planChange={preferences.notifications.plan_change}
            weeklyDigest={preferences.notifications.weekly_digest}
            onToggle={handleNotifToggle} />
        )}
      </div>
      {showSaved && (
        <div className={styles.saveIndicator}><CheckCircle2 size={16} /> 已保存</div>
      )}
    </section>
  );
}
