'use client';

import React, { useState } from 'react';
import { Bell, Map, User, Utensils } from 'lucide-react';

export function SettingsView() {
  const [activeTab, setActiveTab] = useState('profile');
  const [preferences, setPreferences] = useState({
    fitness: true,
    vegetarian: false,
    glutenFree: false,
  });
  const [radiusKm, setRadiusKm] = useState(5);

  const tabs = [
    { id: 'profile', label: '用户资料', icon: User, testId: 'settings-tab-profile' },
    { id: 'diet', label: '饮食偏好', icon: Utensils, testId: 'settings-tab-diet' },
    { id: 'location', label: '位置偏好', icon: Map, testId: 'settings-tab-location' },
    { id: 'notifications', label: '通知', icon: Bell, testId: 'settings-tab-notifications' },
  ];

  function togglePreference(key) {
    setPreferences((current) => ({ ...current, [key]: !current[key] }));
  }

  return (
    <section className="settings-view">
      <header className="page-title">
        <h1>设置</h1>
      </header>

      <div className="settings-layout">
        <nav className="settings-tabs" aria-label="设置分区">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                className={activeTab === tab.id ? 'active' : ''}
                type="button"
                data-testid={tab.testId}
                onClick={() => setActiveTab(tab.id)}
              >
                <Icon size={18} /> {tab.label}
              </button>
            );
          })}
        </nav>

        <div className="settings-content" data-testid="settings-content">
          <section className={activeTab === 'profile' ? '' : 'muted-section'}>
            <h2>用户资料</h2>
            <div className="profile-card">
              <div className="profile-row">
                <div className="profile-avatar" />
                <button type="button">更换头像</button>
              </div>
              <label>
                <span>显示名称</span>
                <input id="display-name" name="displayName" value="张晓然" readOnly />
              </label>
              <label>
                <span>邮箱</span>
                <input id="email" name="email" value="xiaoran@example.com" readOnly />
              </label>
            </div>
          </section>

          <section className={activeTab === 'diet' ? '' : 'muted-section'}>
            <h2>饮食限制</h2>
            <div className="settings-card">
              <Preference testId="preference-fitness" label="减脂友好" detail="优先推荐低热量、高蛋白的餐厅选项。" checked={preferences.fitness} onToggle={() => togglePreference('fitness')} />
              <Preference testId="preference-vegetarian" label="素食" checked={preferences.vegetarian} onToggle={() => togglePreference('vegetarian')} />
              <Preference testId="preference-gluten-free" label="无麸质" checked={preferences.glutenFree} onToggle={() => togglePreference('glutenFree')} />
            </div>
          </section>

          <section className={activeTab === 'location' ? '' : 'muted-section'}>
            <h2>位置偏好</h2>
            <div className="radius-card">
              <div>
                <strong>活动半径</strong>
                <span>周末计划推荐地点的最大距离。</span>
              </div>
              <b>{radiusKm} 公里</b>
              <input
                className="radius-slider"
                data-testid="radius-slider"
                type="range"
                min="1"
                max="10"
                value={radiusKm}
                onChange={(event) => setRadiusKm(Number(event.target.value))}
                onInput={(event) => setRadiusKm(Number(event.currentTarget.value))}
                aria-label="活动半径"
              />
              <footer><span>1 公里</span><span>10 公里</span></footer>
            </div>
          </section>

          <section className={activeTab === 'notifications' ? '' : 'muted-section'}>
            <h2>通知</h2>
            <div className="settings-card">
              <Preference label="执行前提醒" checked />
              <Preference label="计划变更提醒" />
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}

function Preference({ label, detail, checked = false, onToggle = () => {}, testId }) {
  return (
    <div className="preference-row">
      <div>
        <strong>{label}</strong>
        {detail ? <span>{detail}</span> : null}
      </div>
      <button
        className={`toggle${checked ? ' on' : ''}`}
        type="button"
        aria-pressed={checked}
        data-testid={testId}
        onClick={onToggle}
      >
        <span />
      </button>
    </div>
  );
}
