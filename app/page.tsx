'use client';

import React, { useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { ChatView } from '@/components/chat/ChatView';
import { PlanningProgress } from '@/components/planning/PlanningProgress';
import { ClarificationView } from '@/components/clarification/ClarificationView';
import { PlanResultsView } from '@/components/plan/PlanResultsView';
import { ConfirmView } from '@/components/confirm/ConfirmView';
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

  function handleConfirm() {
    machine.goToConfirm();
  }

  function handleExecute() {
    machine.confirmAndExecute();
  }

  function handleRecover(reason: string) {
    machine.recoverCurrentPlan(reason);
  }

  function handleBackToResults() {
    machine.setPhase('results');
  }

  function handlePatchConstraints(updates: Record<string, any>) {
    machine.updateConstraints(updates);
  }

  function handleRegenerateWithFeedback(feedback: string) {
    machine.regenerateWithFeedback(feedback);
  }

  function handleReplaceNode(nodeType: string, nodeId: string) {
    machine.replaceNode(nodeType, nodeId);
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
            recoveredPlan={state.recoveredPlan}
            onConfirm={handleConfirm}
            onRecover={handleRecover}
            onLoadAlternatives={machine.loadAlternatives}
            onPatchConstraints={handlePatchConstraints}
            onRegenerateWithFeedback={handleRegenerateWithFeedback}
            onReplaceNode={handleReplaceNode}
            error={state.error}
            loadingAction={state.loadingAction}
            loadingMessage={state.loadingMessage}
          />
        );

      case 'confirming':
        if (!state.result) return null;
        return (
          <ConfirmView
            result={state.result}
            selectedActions={state.selectedActions}
            onToggleAction={machine.toggleAction}
            onSelectAll={machine.selectAllActions}
            onDeselectAll={machine.deselectAllActions}
            onExecute={handleExecute}
            onBack={handleBackToResults}
            executing={false}
          />
        );

      case 'executing':
        if (!state.result) return null;
        return (
          <ConfirmView
            result={state.result}
            selectedActions={state.selectedActions}
            onToggleAction={machine.toggleAction}
            onSelectAll={machine.selectAllActions}
            onDeselectAll={machine.deselectAllActions}
            onExecute={handleExecute}
            onBack={handleBackToResults}
            executing={true}
          />
        );

      case 'completed':
        return (
          <ReceiptsView
            receipts={state.receipts}
            onNewPlan={handleNewPlan}
          />
        );

      case 'recovering':
        return (
          <PlanningProgress
            goal="正在恢复方案..."
            progress={[]}
            currentStep={0}
            streamingText=""
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
