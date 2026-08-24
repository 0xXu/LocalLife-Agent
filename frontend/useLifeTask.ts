'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { taskApi } from './api';
import type {
  ActionKind,
  GoalEditPayload,
  PlanEditPayload,
  PreferenceFact,
  RealityEventKind,
  TaskSnapshot,
} from './types';

export function useLifeTask() {
  const [task, setTask] = useState<TaskSnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [preferences, setPreferences] = useState<PreferenceFact[]>([]);
  const streamRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!task?.id) return;
    streamRef.current?.close();
    const stream = new EventSource(taskApi.eventUrl(task.id));
    stream.addEventListener('task', (event) => {
      setTask(JSON.parse((event as MessageEvent).data));
    });
    stream.addEventListener('progress', (event) => {
      const progress = JSON.parse((event as MessageEvent).data);
      setTask((current) => current && !current.progress_events.some((item) => item.id === progress.id)
        ? { ...current, progress_events: [...current.progress_events, progress] }
        : current);
    });
    stream.onerror = () => {
      // The next successful response or browser reconnect restores the stream.
    };
    streamRef.current = stream;
    return () => stream.close();
  }, [task?.id]);

  useEffect(() => {
    if (!task?.user_id) return;
    taskApi.preferences().then(setPreferences).catch(() => undefined);
  }, [task?.user_id, (task?.applied_preference_fact_ids ?? []).join('|')]);

  const run = useCallback(async (operation: () => Promise<TaskSnapshot>) => {
    setBusy(true);
    setError('');
    try {
      const snapshot = await operation();
      setTask(snapshot);
      return snapshot;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '任务暂时无法继续');
      return null;
    } finally {
      setBusy(false);
    }
  }, []);

  return {
    task,
    busy,
    error,
    preferences,
    create: (goal: string) => run(() => taskApi.create(goal)),
    reply: (content: string) =>
      task ? run(() => taskApi.message(task.id, content)) : Promise.resolve(null),
    selectDecision: (optionId: string) =>
      task ? run(() => taskApi.selectDecision(task.id, optionId)) : Promise.resolve(null),
    editGoal: (edit: GoalEditPayload) =>
      task ? run(() => taskApi.editGoal(task.id, edit)) : Promise.resolve(null),
    editPlan: (edit: PlanEditPayload) =>
      task
        ? run(() => taskApi.editPlan(task.id, edit))
        : Promise.resolve(null),
    stop: () => (task ? run(() => taskApi.stop(task.id)) : Promise.resolve(null)),
    approveMandate: () =>
      task ? run(() => taskApi.mandate(task.id)) : Promise.resolve(null),
    confirmTransaction: () =>
      task ? run(() => taskApi.transaction(task.id)) : Promise.resolve(null),
    compensate: (eventId: string, action: ActionKind) =>
      task ? run(() => taskApi.compensate(task.id, eventId, action)) : Promise.resolve(null),
    supplyAction: (nodeId: string, action: ActionKind) =>
      task ? run(() => taskApi.supplyAction(task.id, nodeId, action)) : Promise.resolve(null),
    reportReality: (
      event: { kind: RealityEventKind; detail: string; magnitude?: number; node_id?: string; location?: string },
    ) => task ? run(() => taskApi.realityEvent(task.id, event)) : Promise.resolve(null),
    outcomeCheckIn: (response: 'achieved' | 'partly' | 'not_achieved', note?: string) =>
      task ? run(() => taskApi.outcomeCheckIn(task.id, response, note)) : Promise.resolve(null),
    revisePreference: async (
      factId: string,
      edit: { preference?: string; context_scope?: string; delete?: boolean },
    ) => {
      setError('');
      try {
        await taskApi.revisePreference(factId, edit);
        setPreferences(await taskApi.preferences());
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : '偏好更新失败');
      }
    },
    injectScenario: async (scenario: string) => {
      setError('');
      try {
        await taskApi.scenario(scenario);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : '世界状态更新失败');
      }
    },
  };
}
