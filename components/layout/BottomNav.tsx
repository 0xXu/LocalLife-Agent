'use client';

import React from 'react';
import { Bot, Clock, Compass, Settings, User } from 'lucide-react';
import type { ActiveTab } from '../../types/views';

type BottomNavProps = {
  active: ActiveTab;
  onNavigate: (tab: ActiveTab) => void;
};

const tabs: Array<{ id: ActiveTab; label: string; icon: typeof Bot }> = [
  { id: 'home', label: 'AI助手', icon: Bot },
  { id: 'plans', label: '计划', icon: Compass },
  { id: 'activity', label: '记录', icon: Clock },
  { id: 'settings', label: '设置', icon: Settings },
];

export function BottomNav({ active, onNavigate }: BottomNavProps) {
  return (
    <nav className="bottom-nav" role="navigation" aria-label="主导航">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = active === tab.id;
        return (
          <button
            key={tab.id}
            className={`bottom-nav-item${isActive ? ' active' : ''}`}
            type="button"
            onClick={() => onNavigate(tab.id)}
            aria-current={isActive ? 'page' : undefined}
          >
            <span className="bottom-nav-icon">
              <Icon size={22} strokeWidth={isActive ? 2.4 : 1.8} />
              {isActive && <span className="bottom-nav-dot" />}
            </span>
            <span className="bottom-nav-label">{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
