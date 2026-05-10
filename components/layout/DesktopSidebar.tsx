'use client';

import React from 'react';
import { Bot, Clock, Compass, Plus, Settings } from 'lucide-react';
import type { ActiveTab } from '../../types/views';

type DesktopSidebarProps = {
  active: ActiveTab;
  onNavigate: (tab: ActiveTab) => void;
  onNewPlan: () => void;
};

const navItems: Array<{ id: ActiveTab; label: string; icon: typeof Bot }> = [
  { id: 'home', label: 'AI助手', icon: Bot },
  { id: 'plans', label: '我的计划', icon: Compass },
  { id: 'activity', label: '执行记录', icon: Clock },
  { id: 'settings', label: '偏好设置', icon: Settings },
];

export function DesktopSidebar({ active, onNavigate, onNewPlan }: DesktopSidebarProps) {
  return (
    <aside className="desktop-sidebar" aria-label="主导航">
      <div className="sidebar-brand">
        <div className="sidebar-brand-avatar">WP</div>
        <div>
          <strong>WeekendPilot</strong>
          <span>本地生活助手</span>
        </div>
      </div>

      <button className="sidebar-new-plan" type="button" onClick={onNewPlan}>
        <Plus size={18} />
        新计划
      </button>

      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          return (
            <button
              key={item.id}
              className={`sidebar-nav-item${isActive ? ' active' : ''}`}
              type="button"
              onClick={() => onNavigate(item.id)}
              aria-current={isActive ? 'page' : undefined}
            >
              <Icon size={20} strokeWidth={isActive ? 2.4 : 1.8} />
              {item.label}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
