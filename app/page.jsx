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
  recoverUnavailableRestaurant,
  scenarioPrompts
} from '@/features/planner/mockAgent';

export default function WeekendPilotApp() {
  const [activeView, setActiveView] = useState('home');
  const [goal, setGoal] = useState(scenarioPrompts.family);
  const [planResult, setPlanResult] = useState(() => buildPlan(scenarioPrompts.family));
  const [recoveredPlan, setRecoveredPlan] = useState(null);
  const [receipts, setReceipts] = useState([]);

  const currentPlanner = useMemo(() => ({
    goal,
    result: planResult,
    receipts,
    recoveredPlan
  }), [goal, planResult, receipts, recoveredPlan]);

  function createPlan(nextGoal = goal) {
    const result = buildPlan(nextGoal);
    setGoal(nextGoal);
    setPlanResult(result);
    setRecoveredPlan(null);
    setReceipts([]);
    setActiveView('planner');
  }

  function executeCurrentPlan() {
    const plan = recoveredPlan ?? planResult.plan;
    setReceipts(executePlan(plan));
    setActiveView('planner');
  }

  function recoverRestaurant() {
    const plan = recoveredPlan ?? planResult.plan;
    setRecoveredPlan(recoverUnavailableRestaurant(plan));
    setReceipts([]);
    setActiveView('planner');
  }

  return (
    <AppChrome activeView={activeView} onNavigate={setActiveView} onNewPlan={() => setActiveView('home')}>
      {activeView === 'home' ? (
        <HomeView goal={goal} onGoalChange={setGoal} onPlan={createPlan} />
      ) : null}
      {activeView === 'planner' ? (
        <PlannerView
          {...currentPlanner}
          onExecute={executeCurrentPlan}
          onRecover={recoverRestaurant}
        />
      ) : null}
      {activeView === 'saved' ? <SavedPlansView onPlan={() => createPlan(scenarioPrompts.family)} /> : null}
      {activeView === 'activity' ? <ActivityView /> : null}
      {activeView === 'settings' ? <SettingsView /> : null}
      {activeView === 'favorites' || activeView === 'help' ? (
        <HomeView goal={goal} onGoalChange={setGoal} onPlan={createPlan} />
      ) : null}
    </AppChrome>
  );
}
