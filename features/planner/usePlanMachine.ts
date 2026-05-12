import { useCallback, useEffect, useReducer, useRef } from 'react';
import type { PlanPhase, PlanState, LoadingAction } from '../../types/views';
import type { PlanResponse } from '../../types/weekendpilot';
import {
  buildPlanStream,
  buildAlternatives,
  confirmPlan,
  executePlan,
  recoverPlan,
  patchConstraints,
} from './apiClient';
import { NODE_TYPE_LABELS } from '../../lib/constants/nodeTypes';

type Action =
  | { type: 'START_PLAN'; goal: string }
  | { type: 'STREAM_STARTED' }
  | { type: 'STREAM_TOKEN'; content: string }
  | { type: 'UPDATE_PROGRESS'; step: string }
  | { type: 'PLAN_LOADED'; result: PlanResponse }
  | { type: 'PLAN_FAILED'; error: string }
  | { type: 'GO_TO_CONFIRM' }
  | { type: 'START_EXECUTE' }
  | { type: 'EXECUTE_LOADED'; result: PlanResponse }
  | { type: 'EXECUTE_FAILED'; error: string }
  | { type: 'START_RECOVER' }
  | { type: 'RECOVER_LOADED'; result: PlanResponse }
  | { type: 'RECOVER_FAILED'; error: string }
  | { type: 'ALTERNATIVES_LOADED'; result: PlanResponse }
  | { type: 'ALTERNATIVES_FAILED'; error: string }
  | { type: 'CONSTRAINTS_UPDATED'; result: PlanResponse }
  | { type: 'CONSTRAINTS_FAILED'; error: string }
  | { type: 'SET_LOADING'; action: LoadingAction; message: string }
  | { type: 'CLEAR_LOADING' }
  | { type: 'TOGGLE_ACTION'; key: string }
  | { type: 'SELECT_ALL_ACTIONS' }
  | { type: 'DESELECT_ALL_ACTIONS' }
  | { type: 'RESET' }
  | { type: 'SET_PHASE'; phase: PlanPhase };

const initialState: PlanState = {
  phase: 'idle',
  goal: '',
  planId: null,
  result: null,
  recoveredPlan: null,
  receipts: [],
  error: null,
  selectedActions: new Set(),
  progress: [],
  currentStep: -1,
  streamingText: '',
  loadingAction: null,
  loadingMessage: '',
};

function getActionKey(action: Record<string, unknown>): string {
  return `${action.tool ?? action.type}_${action.label ?? action.place_id ?? 'default'}`;
}

function reducer(state: PlanState, action: Action): PlanState {
  switch (action.type) {
    case 'START_PLAN':
      return { ...initialState, phase: 'planning', goal: action.goal, currentStep: 0, streamingText: '' };
    case 'STREAM_STARTED':
      return { ...state, currentStep: 0 };
    case 'STREAM_TOKEN':
      return { ...state, streamingText: state.streamingText + action.content };
    case 'UPDATE_PROGRESS':
      return { ...state, progress: [...state.progress, action.step], currentStep: state.currentStep + 1, streamingText: '' };
    case 'PLAN_LOADED': {
      const plan = action.result.plan;
      const allKeys = new Set<string>(((plan as any)?.actions ?? []).map((a: any) => getActionKey(a)));
      return {
        ...state,
        phase: 'results',
        planId: (plan as any)?.id ?? null,
        result: action.result,
        recoveredPlan: null,
        receipts: [],
        error: null,
        selectedActions: allKeys,
      };
    }
    case 'PLAN_FAILED':
      return { ...state, phase: 'idle', error: action.error };
    case 'GO_TO_CONFIRM':
      return { ...state, phase: 'confirming', error: null };
    case 'START_EXECUTE':
      return { ...state, phase: 'executing', error: null };
    case 'EXECUTE_LOADED':
      return {
        ...state,
        phase: 'completed',
        result: action.result,
        recoveredPlan: null,
        receipts: action.result.receipts,
        error: null,
      };
    case 'EXECUTE_FAILED':
      return { ...state, phase: 'results', error: action.error };
    case 'START_RECOVER':
      return { ...state, phase: 'recovering', error: null };
    case 'RECOVER_LOADED':
      return {
        ...state,
        phase: 'results',
        result: action.result,
        recoveredPlan: (action.result as any).plan ?? null,
        receipts: [],
        error: null,
      };
    case 'RECOVER_FAILED':
      return { ...state, phase: 'results', error: action.error };
    case 'ALTERNATIVES_LOADED':
      if (!state.result) return state;
      return { ...state, phase: 'results', result: mergePlanAlternatives(state.result, action.result), error: null };
    case 'ALTERNATIVES_FAILED':
      return { ...state, phase: 'results', error: action.error };
    case 'CONSTRAINTS_UPDATED':
      return {
        ...state,
        phase: 'results',
        planId: (action.result.plan as any)?.id ?? state.planId,
        result: action.result,
        recoveredPlan: null,
        error: null,
        loadingAction: null,
        loadingMessage: '',
      };
    case 'CONSTRAINTS_FAILED':
      return { ...state, phase: 'results', error: action.error, loadingAction: null, loadingMessage: '' };
    case 'SET_LOADING':
      return { ...state, loadingAction: action.action, loadingMessage: action.message };
    case 'CLEAR_LOADING':
      return { ...state, loadingAction: null, loadingMessage: '' };
    case 'TOGGLE_ACTION': {
      const next = new Set(state.selectedActions);
      if (next.has(action.key)) next.delete(action.key);
      else next.add(action.key);
      return { ...state, selectedActions: next };
    }
    case 'SELECT_ALL_ACTIONS': {
      const plan = state.recoveredPlan ?? state.result?.plan;
      const allKeys = new Set((plan?.actions ?? []).map((a) => getActionKey(a)));
      return { ...state, selectedActions: allKeys };
    }
    case 'DESELECT_ALL_ACTIONS':
      return { ...state, selectedActions: new Set() };
    case 'RESET':
      return initialState;
    case 'SET_PHASE':
      return { ...state, phase: action.phase };
    default:
      return state;
  }
}

export function usePlanMachine() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => { mountedRef.current = false; };
  }, []);

  const startPlan = useCallback(async (goal: string) => {
    dispatch({ type: 'START_PLAN', goal });
    try {
      const result = await buildPlanStream(goal, {
        onStarted: async () => {
          if (mountedRef.current) dispatch({ type: 'STREAM_STARTED' });
        },
        onToken: async (content: string) => {
          if (mountedRef.current) dispatch({ type: 'STREAM_TOKEN', content });
        },
        onProgress: async (label: string) => {
          if (mountedRef.current) dispatch({ type: 'UPDATE_PROGRESS', step: label });
          // 添加 400ms 延迟，让用户能看到每个步骤的变化
          await new Promise<void>((resolve) => {
            requestAnimationFrame(() => {
              setTimeout(resolve, 400);
            });
          });
        },
      });
      if (mountedRef.current) dispatch({ type: 'PLAN_LOADED', result });
    } catch (err) {
      if (mountedRef.current) dispatch({ type: 'PLAN_FAILED', error: err instanceof Error ? err.message : '计划生成失败' });
    }
  }, []);

  const goToConfirm = useCallback(() => {
    dispatch({ type: 'GO_TO_CONFIRM' });
  }, []);

  const confirmAndExecute = useCallback(async () => {
    const planId = (state.recoveredPlan ?? state.result?.plan)?.id;
    if (!planId) return;
    dispatch({ type: 'START_EXECUTE' });
    try {
      await confirmPlan(planId);
      const result = await executePlan(planId);
      dispatch({ type: 'EXECUTE_LOADED', result });
    } catch (err) {
      dispatch({ type: 'EXECUTE_FAILED', error: err instanceof Error ? err.message : '执行失败' });
    }
  }, [state.recoveredPlan, state.result]);

  const recoverCurrentPlan = useCallback(async (reason: string) => {
    const planId = (state.recoveredPlan ?? state.result?.plan)?.id;
    if (!planId) return;
    dispatch({ type: 'START_RECOVER' });
    try {
      const result = await recoverPlan(planId, reason);
      dispatch({ type: 'RECOVER_LOADED', result });
    } catch (err) {
      dispatch({ type: 'RECOVER_FAILED', error: err instanceof Error ? err.message : '恢复失败' });
    }
  }, [state.recoveredPlan, state.result]);

  const loadAlternatives = useCallback(async () => {
    if (!state.planId) return;
    dispatch({ type: 'SET_LOADING', action: 'alternatives', message: '正在加载更多方案...' });
    try {
      const result = await buildAlternatives(state.planId);
      dispatch({ type: 'ALTERNATIVES_LOADED', result });
    } catch (err) {
      dispatch({ type: 'ALTERNATIVES_FAILED', error: err instanceof Error ? err.message : '备选方案加载失败' });
    } finally {
      dispatch({ type: 'CLEAR_LOADING' });
    }
  }, [state.planId]);

  const updateConstraints = useCallback(async (updates: Record<string, any>) => {
    const planId = (state.recoveredPlan ?? state.result?.plan)?.id;
    if (!planId) return;
    dispatch({ type: 'SET_LOADING', action: 'constraints', message: '正在根据新约束重新生成方案...' });
    try {
      const result = await patchConstraints(planId, updates);
      dispatch({ type: 'CONSTRAINTS_UPDATED', result });
    } catch (err) {
      dispatch({ type: 'CONSTRAINTS_FAILED', error: err instanceof Error ? err.message : '约束更新失败' });
    }
  }, [state.recoveredPlan, state.result]);

  const regenerateWithFeedback = useCallback(async (feedback: string) => {
    dispatch({ type: 'SET_LOADING', action: 'feedback', message: '正在根据您的反馈调整方案...' });

    // 将反馈转换为约束更新
    const updates: Record<string, any> = {};

    // 简单的关键词匹配来解析反馈
    const feedbackLower = feedback.toLowerCase();

    if (feedbackLower.includes('轻松') || feedbackLower.includes('不赶') || feedbackLower.includes('慢')) {
      updates.duration_hours = 6; // 增加时长
    }
    if (feedbackLower.includes('赶') || feedbackLower.includes('快') || feedbackLower.includes('紧凑')) {
      updates.duration_hours = 3; // 减少时长
    }
    if (feedbackLower.includes('省钱') || feedbackLower.includes('便宜') || feedbackLower.includes('预算')) {
      updates.budget_level = 'low';
    }
    if (feedbackLower.includes('贵') || feedbackLower.includes('高端') || feedbackLower.includes('不限预算')) {
      updates.budget_level = 'high';
    }
    if (feedbackLower.includes('近') || feedbackLower.includes('不远') || feedbackLower.includes('附近')) {
      updates.radius_km = 3;
    }
    if (feedbackLower.includes('远') || feedbackLower.includes('范围大')) {
      updates.radius_km = 10;
    }

    // 如果没有匹配到任何约束，使用原始反馈重新生成计划
    if (Object.keys(updates).length === 0) {
      // 重新开始计划，将反馈作为目标的一部分
      await startPlan(feedback);
    } else {
      await updateConstraints(updates);
    }
  }, [startPlan, updateConstraints]);

  const replaceNode = useCallback(async (nodeType: string, nodeId: string) => {
    const planId = (state.recoveredPlan ?? state.result?.plan)?.id;
    if (!planId) return;

    dispatch({
      type: 'SET_LOADING',
      action: 'replace',
      message: `正在为您更换${NODE_TYPE_LABELS[nodeType] || '节点'}...`
    });

    const reasonMap: Record<string, string> = {
      'activity': 'activity_full',
      'restaurant': 'restaurant_unavailable',
      'dessert_walk': 'route_timeout',
    };

    const reason = reasonMap[nodeType] || 'restaurant_unavailable';
    await recoverCurrentPlan(reason);
  }, [state.recoveredPlan, state.result, recoverCurrentPlan]);

  const toggleAction = useCallback((key: string) => {
    dispatch({ type: 'TOGGLE_ACTION', key });
  }, []);

  const selectAllActions = useCallback(() => {
    dispatch({ type: 'SELECT_ALL_ACTIONS' });
  }, []);

  const deselectAllActions = useCallback(() => {
    dispatch({ type: 'DESELECT_ALL_ACTIONS' });
  }, []);

  const reset = useCallback(() => {
    dispatch({ type: 'RESET' });
  }, []);

  const setPhase = useCallback((phase: PlanPhase) => {
    dispatch({ type: 'SET_PHASE', phase });
  }, []);

  return {
    state,
    startPlan,
    goToConfirm,
    confirmAndExecute,
    recoverCurrentPlan,
    loadAlternatives,
    updateConstraints,
    regenerateWithFeedback,
    replaceNode,
    toggleAction,
    selectAllActions,
    deselectAllActions,
    reset,
    setPhase,
    getActionKey,
  };
}

export function mergePlanAlternatives(current: PlanResponse, alternativesResponse: PlanResponse): PlanResponse {
  const incoming = ((alternativesResponse as any).variants ?? (alternativesResponse as any).alternatives ?? []) as any[];
  const existing = (current.variants?.length ? current.variants : [current.plan]) as any[];
  const seen = new Set<string>();
  const variants = [...existing, ...incoming].filter((variant: any, index) => {
    const key = String(variant.kind ?? variant.id ?? variant.title ?? index);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  return {
    ...current,
    ...alternativesResponse,
    plan: current.plan,
    constraints: current.constraints,
    itinerary: current.itinerary,
    pending_actions: current.pending_actions,
    progress: current.progress,
    trace: current.trace,
    tool_calls: current.tool_calls,
    variants,
  };
}
