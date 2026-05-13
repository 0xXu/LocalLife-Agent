'use client';

import React, { useCallback } from 'react';
import {
  Bell,
  Brain,
  CheckCircle2,
  MapPin,
  Radar,
  ShieldCheck,
  Sparkles,
  Utensils,
  User,
} from 'lucide-react';
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
  const { preferences, loading, saving, showSaved, update } = usePreferences();
  const [activeTab, setActiveTab] = React.useState<SettingsTab>('profile');
  const activeDietCount = [
    preferences.diet.fitness_friendly,
    preferences.diet.vegetarian,
    preferences.diet.gluten_free,
  ].filter(Boolean).length;
  const activeNotificationCount = [
    preferences.notifications.execution_reminder,
    preferences.notifications.plan_change,
    preferences.notifications.weekly_digest,
  ].filter(Boolean).length;
  const completionScore = Math.round(
    ([
      Boolean(preferences.profile.display_name),
      Boolean(preferences.profile.email),
      preferences.location.radius_km > 0,
      activeDietCount > 0,
      activeNotificationCount > 0,
    ].filter(Boolean).length / 5) * 100,
  );

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
      <div className={styles.header}>
        <div>
          <span className={styles.kicker}>User profile</span>
          <h1 className={styles.title}>偏好设置</h1>
          <p className={styles.subtitle}>把偏好沉淀成用户画像，后端会在开放域规划、候选排序和计划修订中自动应用。</p>
        </div>
        <div className={styles.syncPill} aria-live="polite">
          <CheckCircle2 size={16} />
          {saving ? '正在同步' : '画像已同步'}
        </div>
      </div>

      <div className={styles.profileMetrics} aria-label="用户画像摘要">
        <article>
          <Brain size={18} />
          <span>画像记忆</span>
          <strong>{activeDietCount + activeNotificationCount + 1} 条信号</strong>
        </article>
        <article>
          <Radar size={18} />
          <span>活动半径</span>
          <strong>{preferences.location.radius_km} 公里</strong>
        </article>
        <article>
          <Sparkles size={18} />
          <span>偏好完成度</span>
          <strong>{completionScore}%</strong>
        </article>
      </div>

      <div className={styles.workspace}>
        <div className={styles.mainPanel}>
          <div className={styles.tabsShell}>
            <SegmentedControl options={TAB_OPTIONS} value={activeTab} onChange={setActiveTab} testIdPrefix="settings-tab" />
          </div>
          <div className={styles.layout} data-testid="settings-content">
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
        </div>

        <aside className={styles.memoryPanel} aria-label="画像如何影响规划">
          <div className={styles.memoryHeader}>
            <div className={styles.memoryIcon}><ShieldCheck size={18} /></div>
            <div>
              <span>Planning memory</span>
              <h2>画像如何影响计划</h2>
            </div>
          </div>
          <ul className={styles.memoryList}>
            <li>
              <strong>开放域检索</strong>
              <span>优先把饮食、距离和通知偏好转成候选筛选条件。</span>
            </li>
            <li>
              <strong>候选排序</strong>
              <span>用活动半径、饮食标签和历史选择调整综合评分。</span>
            </li>
            <li>
              <strong>计划修订</strong>
              <span>用户反馈“不行”时，把新的偏好写回画像并用于下一版。</span>
            </li>
          </ul>
          <div className={styles.memoryFooter}>
            <span>当前活跃偏好</span>
            <strong>{activeDietCount} 个饮食 · {activeNotificationCount} 个通知</strong>
          </div>
        </aside>
      </div>
      {showSaved && (
        <div className={styles.saveIndicator}><CheckCircle2 size={16} /> 已保存</div>
      )}
    </section>
  );
}
