'use client';

import React, { useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { ChatView } from '@/components/chat/ChatView';
import { PlanningProgress } from '@/components/planning/PlanningProgress';
import { ClarificationView } from '@/components/clarification/ClarificationView';
import { PlanResultsView } from '@/components/plan/PlanResultsView';
import { ReceiptsView } from '@/components/receipts/ReceiptsView';
import { SavedPlansView } from '@/components/saved/SavedPlansView';
import { ActivityView } from '@/components/activity/ActivityView';
import { SettingsView } from '@/components/settings/SettingsView';
import { usePlanMachine } from '@/features/planner/usePlanMachine';
import type { ActiveTab } from '@/types/views';

export default function WeekendPilotApp() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('home');
  const machine = usePlanMachine();
  const { state } = machine;

  function handleNavigate(tab: ActiveTab) {
    setActiveTab(tab);
  }

  function handleNewPlan() {
    machine.reset();
    setActiveTab('home');
  }

  function handleSubmitGoal(goal: string) {
    machine.startPlan(goal);
  }

  function handleExecute() {
    machine.approveSelectedActions();
  }

  const planContent = (() => {
    switch (state.phase) {
      case 'idle':
        return (
          <ChatView
            onSubmitGoal={handleSubmitGoal}
            isPlanning={false}
            error={state.error}
          />
        );

      case 'planning':
        return (
          <PlanningProgress
            goal={state.goal}
            progress={state.progress}
            currentStep={state.currentStep}
            streamingText={state.streamingText}
          />
        );

      case 'clarifying':
        if (!state.clarification) return null;
        return (
          <ClarificationView
            goal={state.goal}
            clarification={state.clarification}
            onSubmitGoal={handleSubmitGoal}
          />
        );

      case 'results':
        if (!state.result) return null;
        return (
          <PlanResultsView
            result={state.result}
            selectedActions={state.selectedActions}
            executing={false}
            onToggleAction={machine.toggleAction}
            onSelectAll={machine.selectAllActions}
            onDeselectAll={machine.deselectAllActions}
            onApprove={handleExecute}
            onReject={machine.rejectCurrentPlan}
            error={state.error}
          />
        );

      case 'executing':
        if (!state.result) return null;
        return (
          <PlanResultsView
            result={state.result}
            selectedActions={state.selectedActions}
            executing={true}
            onToggleAction={machine.toggleAction}
            onSelectAll={machine.selectAllActions}
            onDeselectAll={machine.deselectAllActions}
            onApprove={handleExecute}
            onReject={machine.rejectCurrentPlan}
            error={state.error}
          />
        );

      case 'completed':
        return (
          <ReceiptsView
            receipts={state.receipts}
            onNewPlan={handleNewPlan}
          />
        );

      default:
        return null;
    }
  })();

  return (
    <AppShell
      activeTab={activeTab}
      onNavigate={handleNavigate}
      onNewPlan={handleNewPlan}
    >
      {activeTab === 'home' && planContent}
      {activeTab === 'plans' && <SavedPlansView onNavigateHome={handleNewPlan} />}
      {activeTab === 'activity' && <ActivityView />}
      {activeTab === 'settings' && <SettingsView />}
    </AppShell>
  );
}
