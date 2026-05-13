'use client';

import React from 'react';
import { User } from 'lucide-react';
import styles from './SettingsView.module.css';

export interface ProfileSectionProps {
  displayName: string;
  email: string;
  onChange: (field: 'display_name' | 'email', value: string) => void;
}

export function ProfileSection({ displayName, email, onChange }: ProfileSectionProps) {
  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}><User size={18} /> 用户资料</h2>
      <p className={styles.sectionLead}>用于称呼、通知和多人计划里的身份上下文。</p>
      <div className={styles.field}>
        <label htmlFor="display-name">显示名称</label>
        <input id="display-name" value={displayName} onChange={(e) => onChange('display_name', e.target.value)} />
      </div>
      <div className={styles.field}>
        <label htmlFor="email">邮箱</label>
        <input id="email" type="email" value={email} onChange={(e) => onChange('email', e.target.value)} />
      </div>
    </div>
  );
}
