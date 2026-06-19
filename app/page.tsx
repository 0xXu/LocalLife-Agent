'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { ChatView } from '@/components/chat/ChatView';
import { PlanningProgress } from '@/components/planning/PlanningProgress';
import { PlanResultsView } from '@/components/plan/PlanResultsView';
import { ReceiptsView } from '@/components/receipts/ReceiptsView';
import { SavedPlansView } from '@/components/saved/SavedPlansView';
import { ActivityView } from '@/components/activity/ActivityView';
import { SettingsView } from '@/components/settings/SettingsView';
import { getPlan } from '@/features/plans/api';
import { useRunController } from '@/features/runs/useRunController';
import type { ActiveTab } from '@/types/views';
import type { PlanResponse } from '@/types/weekendpilot';

export default function WeekendPilotApp() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('home');
  const runController = useRunController();
  const { state } = runController;
  const [goal, setGoal] = useState('');
  const [result, setResult] = useState<PlanResponse | null>(null);
  const [selectedActions, setSelectedActions] = useState<Set<string>>(new Set());
  const [planError, setPlanError] = useState<string | null>(null);
  const [clarificationSubmitting, setClarificationSubmitting] = useState(false);

  useEffect(() => {
    if (!state.planId || !shouldLoadPlan(state.status)) {
      return;
    }

    let cancelled = false;
    getPlan(state.planId)
      .then((planResult) => {
        if (cancelled) return;
        setResult(planResult);
        setSelectedActions(new Set(selectableActions(planResult).map(getActionKey)));
        setPlanError(null);
      })
      .catch((err) => {
        if (!cancelled) {
          setPlanError(err instanceof Error ? err.message : '计划加载失败');
        }
      });

    return () => {
      cancelled = true;
    };
  }, [state.planId, state.status, state.events.length]);

  const resultWithRunTrace = useMemo(() => {
    if (!result) return null;
    return {
      ...result,
      trace: [
        ...(result.trace ?? []),
        ...state.events.map((event) => ({
          id: `run_${event.seq}_${event.type}`,
          kind: event.type,
          message: runEventLabel(event.type),
          agent: 'Run Controller',
          status: runEventStatus(event.type),
          input_summary: event.payload,
          output_summary: {},
        })),
      ],
    } as PlanResponse;
  }, [result, state.events]);

  function handleNavigate(tab: ActiveTab) {
    setActiveTab(tab);
  }

  function handleNewPlan() {
    runController.reset();
    setGoal('');
    setResult(null);
    setSelectedActions(new Set());
    setPlanError(null);
    setClarificationSubmitting(false);
    setActiveTab('home');
  }

  function handleSubmitGoal(goal: string) {
    setGoal(goal);
    setResult(null);
    setSelectedActions(new Set());
    setPlanError(null);
    setClarificationSubmitting(false);
    void runController.start(goal);
  }

  async function handleAnswerClarification(questionId: string, answer: unknown) {
    setPlanError(null);
    setClarificationSubmitting(true);
    try {
      await runController.answerClarification(questionId, answer);
    } catch (err) {
      setPlanError(err instanceof Error ? err.message : '补充信息提交失败');
    } finally {
      setClarificationSubmitting(false);
    }
  }

  function handleExecute() {
    const actionIds = Array.from(selectedActions);
    if (!actionIds.length) {
      setPlanError('请选择至少一项待执行动作');
      return;
    }
    setPlanError(null);
    void runController.approve(actionIds).catch((err) => {
      setPlanError(err instanceof Error ? err.message : '执行失败');
    });
  }

  function handleReject() {
    setPlanError(null);
    void runController.reject().catch((err) => {
      setPlanError(err instanceof Error ? err.message : '取消失败');
    });
  }

  function handleToggleAction(key: string) {
    setSelectedActions((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function handleSelectAllActions() {
    setSelectedActions(new Set(selectableActions(result).map(getActionKey)));
  }

  function handleDeselectAllActions() {
    setSelectedActions(new Set());
  }

  const planContent = (() => {
    const phase = phaseForRunState(state.status, resultWithRunTrace);
    const error = planError ?? errorMessage(state.error);

    switch (phase) {
      case 'idle':
        return (
          <ChatView
            onSubmitGoal={handleSubmitGoal}
            isPlanning={false}
            error={error}
            goal={goal}
          />
        );

      case 'planning':
        return (
          <PlanningProgress
            goal={goal}
            progress={progressForRunEvents(state.events)}
            currentStep={Math.min(Math.max(state.events.length, 0), 6)}
            streamingText={streamingTextForRunEvents(state.events)}
          />
        );

      case 'clarifying':
        if (!state.currentQuestion) {
          return <ChatView onSubmitGoal={handleSubmitGoal} isPlanning={true} error={error} goal={goal} />;
        }
        return (
          <ChatView
            onSubmitGoal={handleSubmitGoal}
            isPlanning={false}
            error={error}
            goal={goal}
            clarificationQuestion={state.currentQuestion}
            clarificationSubmitting={clarificationSubmitting}
            onAnswerClarification={handleAnswerClarification}
          />
        );

      case 'results':
        if (!resultWithRunTrace) return null;
        return (
          <PlanResultsView
            result={resultWithRunTrace}
            selectedActions={selectedActions}
            executing={false}
            onToggleAction={handleToggleAction}
            onSelectAll={handleSelectAllActions}
            onDeselectAll={handleDeselectAllActions}
            onApprove={handleExecute}
            onReject={handleReject}
            error={error}
          />
        );

      case 'executing':
        if (!resultWithRunTrace) return null;
        return (
          <PlanResultsView
            result={resultWithRunTrace}
            selectedActions={selectedActions}
            executing={true}
            onToggleAction={handleToggleAction}
            onSelectAll={handleSelectAllActions}
            onDeselectAll={handleDeselectAllActions}
            onApprove={handleExecute}
            onReject={handleReject}
            error={error}
          />
        );

      case 'completed':
        if (!resultWithRunTrace) return null;
        return (
          <ReceiptsView
            receipts={resultWithRunTrace.receipts ?? []}
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

function shouldLoadPlan(status: string) {
  return ['approval_required', 'executing', 'completed', 'rejected', 'failed', 'validation_failed'].includes(status);
}

function phaseForRunState(status: string, result: PlanResponse | null) {
  if (status === 'idle' || (status === 'failed' && !result)) return 'idle';
  if (status === 'queued' || status === 'running') return 'planning';
  if (status === 'needs_clarification') return 'clarifying';
  if (status === 'executing') return result ? 'executing' : 'planning';
  if (status === 'completed') return result ? 'completed' : 'planning';
  return result ? 'results' : 'planning';
}

function selectableActions(result: PlanResponse | null): Array<Record<string, unknown>> {
  if (!result) return [];
  const actions = ((result.actions?.length ? result.actions : result.plan.actions) ?? []) as Array<Record<string, unknown>>;
  return actions.filter((action) => String(action.status ?? 'pending') === 'pending');
}

function getActionKey(action: Record<string, unknown>) {
  return String(action.action_id ?? action.id ?? `${action.tool ?? action.type}_${action.target ?? action.label ?? action.place_id ?? 'default'}`);
}

function progressForRunEvents(events: Array<{ type: string }>) {
  if (!events.length) return ['Run queued'];
  return events.map((event) => runEventLabel(event.type));
}

function streamingTextForRunEvents(events: Array<{ type: string; payload: Record<string, unknown> }>) {
  const latest = events.at(-1);
  if (!latest) return '正在启动新的运行...';
  const detail = latest.payload.message ?? latest.payload.summary ?? latest.payload.agent ?? latest.type;
  return String(detail);
}

function runEventLabel(type: string) {
  const labels: Record<string, string> = {
    'run.started': 'Run started',
    'run.running': 'Run running',
    'agent.started': 'Agent started',
    'agent.completed': 'Agent completed',
    'agent.handoff': 'Agent handoff',
    'tool.called': 'Tool called',
    'tool.completed': 'Tool completed',
    'tool.failed': 'Tool failed',
    'guardrail.triggered': 'Guardrail triggered',
    'plan.draft.created': 'Plan draft created',
    'plan.validation.completed': 'Plan validation completed',
    'clarification.required': 'Clarification required',
    'approval.required': 'Approval required',
    'run.executing': 'Run executing',
    'actions.execution.started': 'Action execution started',
    'actions.execution.completed': 'Action execution completed',
    'run.completed': 'Run completed',
    'run.failed': 'Run failed',
    'run.rejected': 'Run rejected',
  };
  return labels[type] ?? type;
}

function runEventStatus(type: string) {
  if (type === 'run.failed' || type === 'tool.failed' || type === 'guardrail.triggered') return 'failed';
  if (type === 'run.completed' || type === 'actions.execution.completed') return 'succeeded';
  if (type === 'run.rejected') return 'skipped';
  return 'running';
}

function errorMessage(error: unknown) {
  if (!error) return null;
  if (error instanceof Error) return error.message;
  return typeof error === 'string' ? error : '运行失败';
}
