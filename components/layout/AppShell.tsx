'use client';

import React from 'react';
import type { ActiveTab } from '../../types/views';
import { BottomNav } from './BottomNav';
import { DesktopSidebar } from './DesktopSidebar';

type AppShellProps = {
  activeTab: ActiveTab;
  onNavigate: (tab: ActiveTab) => void;
  onNewPlan: () => void;
  children: React.ReactNode;
};

export function AppShell({ activeTab, onNavigate, onNewPlan, children }: AppShellProps) {
  return (
    <div className="app-shell">
      <DesktopSidebar active={activeTab} onNavigate={onNavigate} onNewPlan={onNewPlan} />
      <main className="app-main">
        <div className="app-content">
          {children}
        </div>
        <BottomNav active={activeTab} onNavigate={onNavigate} />
      </main>
    </div>
  );
}
