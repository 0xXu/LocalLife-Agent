'use client';

import {
  Bookmark,
  Heart,
  HelpCircle,
  History,
  Home,
  Plus,
  Settings
} from 'lucide-react';

const navItems = [
  { id: 'home', label: '首页', icon: Home },
  { id: 'saved', label: '保存计划', icon: Bookmark },
  { id: 'activity', label: '最近执行', icon: History },
  { id: 'favorites', label: '收藏地点', icon: Heart }
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
        <NavButton
          item={{ id: 'settings', label: '设置', icon: Settings }}
          active={activeView === 'settings'}
          onNavigate={onNavigate}
        />
        <NavButton
          item={{ id: 'help', label: '帮助', icon: HelpCircle }}
          active={activeView === 'help'}
          onNavigate={onNavigate}
        />
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
