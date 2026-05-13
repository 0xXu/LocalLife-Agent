'use client';

import React from 'react';
import { Bell } from 'lucide-react';
import { Toggle } from '../ui/Toggle';
import styles from './SettingsView.module.css';

export interface NotificationSectionProps {
  executionReminder: boolean;
  planChange: boolean;
  weeklyDigest: boolean;
  onToggle: (key: 'execution_reminder' | 'plan_change' | 'weekly_digest') => void;
}

export function NotificationSection({ executionReminder, planChange, weeklyDigest, onToggle }: NotificationSectionProps) {
  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}><Bell size={18} /> 通知设置</h2>
      <p className={styles.sectionLead}>控制执行动作后的提醒、计划变更和周期摘要。</p>
      <Toggle checked={executionReminder} onChange={() => onToggle('execution_reminder')}
        label="执行前提醒" description="计划执行前 30 分钟发送提醒" testId="notif-execution" />
      <Toggle checked={planChange} onChange={() => onToggle('plan_change')}
        label="计划变更提醒" description="计划有更新时通知你" testId="notif-change" />
      <Toggle checked={weeklyDigest} onChange={() => onToggle('weekly_digest')}
        label="每周摘要" description="每周一发送上周执行总结" testId="notif-digest" />
    </div>
  );
}
