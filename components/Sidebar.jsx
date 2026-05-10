'use client';

import React from 'react';
import {
  Bookmark,
  History,
  Home,
  Plus,
  Settings
} from 'lucide-react';

const navItems = [
  { id: 'home', label: '工作台', icon: Home }
];

export const workspaceTabs = [
  { id: 'saved', label: '保存计划', icon: Bookmark },
  { id: 'activity', label: '最近执行', icon: History },
  { id: 'settings', label: '偏好设置', icon: Settings }
];

export function Sidebar({ activeView, onNavigate, onNewPlan }) {
  return (
    <aside className="sidebar" aria-label="主导航">
      <div className="brand-block">
        <div className="brand-avatar">WP</div>
        <div>
          <strong>WeekendPilot</strong>
          <span>本地生活助手</span>
        </div>
      </div>

      <button className="new-plan-button" type="button" onClick={onNewPlan}>
        <Plus size={18} />
        新计划
      </button>

      <nav className="nav-list">
        {navItems.map((item) => (
          <NavButton
            key={item.id}
            item={item}
            active={activeView === item.id}
            onNavigate={onNavigate}
          />
        ))}
      </nav>

      <div className="sidebar-footer">
        <span className="sidebar-note">计划、执行记录和偏好已收敛到工作台顶部标签。</span>
      </div>
    </aside>
  );
}

function NavButton({ item, active, onNavigate }) {
  const Icon = item.icon;

  return (
    <button
      className={`nav-item${active ? ' active' : ''}`}
      type="button"
      onClick={() => onNavigate(item.id)}
    >
      <Icon size={21} strokeWidth={2.2} />
      {item.label}
    </button>
  );
}
