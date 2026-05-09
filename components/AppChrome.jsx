'use client';

import { MoreVertical, Search } from 'lucide-react';
import { Sidebar, workspaceTabs } from './Sidebar';

export function AppChrome({ activeView, children, onNavigate, onNewPlan }) {
  return (
    <div className="app-shell">
      <Sidebar activeView={activeView} onNavigate={onNavigate} onNewPlan={onNewPlan} />
      <main className="main-surface">
        <header className="global-topbar">
          <div className="topbar-brand">WeekendPilot</div>
          <div className="topbar-search">
            <Search size={18} />
            <span>搜索计划、地点或偏好...</span>
          </div>
          <button className="execute-pill" type="button" onClick={onNewPlan}>
            执行
          </button>
          <button className="icon-button" type="button" aria-label="更多操作">
            <MoreVertical size={19} />
          </button>
        </header>
        <nav className="workspace-tabs" aria-label="工作台辅助视图">
          {workspaceTabs.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={activeView === item.id ? 'active' : ''}
                type="button"
                onClick={() => onNavigate(item.id)}
              >
                <Icon size={17} />
                {item.label}
              </button>
            );
          })}
        </nav>
        {children}
      </main>
    </div>
  );
}
