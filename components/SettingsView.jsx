'use client';

import { Bell, Map, User, Utensils } from 'lucide-react';

export function SettingsView() {
  return (
    <section className="settings-view">
      <header className="page-title">
        <h1>设置</h1>
      </header>

      <div className="settings-layout">
        <nav className="settings-tabs" aria-label="设置分区">
          <button className="active" type="button"><User size={18} /> 用户资料</button>
          <button type="button"><Utensils size={18} /> 饮食偏好</button>
          <button type="button"><Map size={18} /> 位置偏好</button>
          <button type="button"><Bell size={18} /> 通知</button>
        </nav>

        <div className="settings-content">
          <section>
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

          <section>
            <h2>饮食限制</h2>
            <div className="settings-card">
              <Preference label="减脂友好" detail="优先推荐低热量、高蛋白的餐厅选项。" checked />
              <Preference label="素食" />
              <Preference label="无麸质" />
            </div>
          </section>

          <section>
            <h2>位置偏好</h2>
            <div className="radius-card">
              <div>
                <strong>活动半径</strong>
                <span>周末计划推荐地点的最大距离。</span>
              </div>
              <b>5 公里</b>
              <div className="range-track"><span /></div>
              <footer><span>1 公里</span><span>10 公里</span></footer>
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}

function Preference({ label, detail, checked = false }) {
  return (
    <div className="preference-row">
      <div>
        <strong>{label}</strong>
        {detail ? <span>{detail}</span> : null}
      </div>
      <button className={`toggle${checked ? ' on' : ''}`} type="button" aria-pressed={checked}>
        <span />
      </button>
    </div>
  );
}
