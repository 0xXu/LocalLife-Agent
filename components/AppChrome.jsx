'use client';

import React, { useState } from 'react';
import { MoreVertical, Search } from 'lucide-react';
import { Sidebar, workspaceTabs } from './Sidebar';

export function AppChrome({ activeView, children, onNavigate, onNewPlan, onSearch = () => {} }) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState('');

  function updateQuery(value) {
    setQuery(value);
    onSearch(value);
  }

  return (
    <div className="app-shell">
      <Sidebar activeView={activeView} onNavigate={onNavigate} onNewPlan={onNewPlan} />
      <main className="main-surface">
        <header className="global-topbar">
          <div className="topbar-brand">WeekendPilot</div>
          <div
            className="topbar-search"
            data-testid="global-search-trigger"
            onClick={() => setSearchOpen(true)}
            role="search"
          >
            <Search size={18} />
            {searchOpen ? (
              <input
                data-testid="global-search-input"
                type="search"
                value={query}
                onChange={(event) => updateQuery(event.target.value)}
                onInput={(event) => updateQuery(event.currentTarget.value)}
                onClick={(event) => event.stopPropagation()}
                autoFocus
                placeholder="搜索计划、地点或偏好..."
              />
            ) : (
              <span>{query || '搜索计划、地点或偏好...'}</span>
            )}
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
