'use client';

import { useMemo, useState } from 'react';
import { ActivityView } from '@/components/ActivityView';
import { AppChrome } from '@/components/AppChrome';
import { HomeView } from '@/components/HomeView';
import { PlannerView } from '@/components/PlannerView';
import { SavedPlansView } from '@/components/SavedPlansView';
import { SettingsView } from '@/components/SettingsView';
import {
  buildPlan,
  executePlan,
  recoverPlan,
  scenarioPrompts
} from '@/features/planner/apiClient';
import type { PlanResponse } from '@/types/weekendpilot';

type Plan = PlanResponse['plan'];
type Receipt = PlanResponse['receipts'][number];

export default function WeekendPilotApp() {
  const [activeView, setActiveView] = useState('home');
  const [goal, setGoal] = useState(scenarioPrompts.family);
  const [planResult, setPlanResult] = useState<PlanResponse | null>(null);
  const [recoveredPlan, setRecoveredPlan] = useState<Plan | null>(null);
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isPlanning, setIsPlanning] = useState(false);

  const currentPlanner = useMemo(() => ({
    goal,
    result: planResult,
    receipts,
    recoveredPlan
  }), [goal, planResult, receipts, recoveredPlan]);

  async function createPlan(nextGoal = goal) {
    try {
      setGoal(nextGoal);
      setError(null);
      setIsPlanning(true);
      setPlanResult(null);
      setRecoveredPlan(null);
      setReceipts([]);
      setActiveView('planner');
      const result = await buildPlan(nextGoal);
      setPlanResult(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '计划生成失败');
      setActiveView('home');
    } finally {
      setIsPlanning(false);
    }
  }

  function startNewPlan() {
    setGoal(scenarioPrompts.family);
    setPlanResult(null);
    setRecoveredPlan(null);
    setReceipts([]);
    setError(null);
    setIsPlanning(false);
    setActiveView('home');
  }

  async function executeCurrentPlan() {
    const planId = (recoveredPlan ?? planResult?.plan)?.id;
    if (!planId) {
      return;
    }
    try {
      setError(null);
      const result = await executePlan(planId);
      setPlanResult(result);
      setRecoveredPlan(null);
      setReceipts(result.receipts);
      setActiveView('planner');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '计划执行失败');
    }
  }

  async function recoverRestaurant() {
    const planId = (recoveredPlan ?? planResult?.plan)?.id;
    if (!planId) {
      return;
    }
    try {
      setError(null);
      const result = await recoverPlan(planId, 'restaurant_unavailable');
      setPlanResult(result);
      setRecoveredPlan(result.plan);
      setReceipts([]);
      setActiveView('planner');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '恢复计划失败');
    }
  }

  return (
    <AppChrome activeView={activeView} onNavigate={setActiveView} onNewPlan={startNewPlan}>
      {error ? <div className="app-error" role="alert">{error}</div> : null}
      {activeView === 'home' ? (
        <HomeView goal={goal} isPlanning={isPlanning} onGoalChange={setGoal} onPlan={createPlan} />
      ) : null}
      {activeView === 'planner' && planResult ? (
        <PlannerView
          {...currentPlanner}
          onExecute={executeCurrentPlan}
          onRecover={recoverRestaurant}
        />
      ) : null}
      {activeView === 'planner' && !planResult ? <section className="planner-view">正在生成计划...</section> : null}
      {activeView === 'saved' ? <SavedPlansView onPlan={() => createPlan(scenarioPrompts.family)} /> : null}
      {activeView === 'activity' ? <ActivityView /> : null}
      {activeView === 'settings' ? <SettingsView /> : null}
    </AppChrome>
  );
}
