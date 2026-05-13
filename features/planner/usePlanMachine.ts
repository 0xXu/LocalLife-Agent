import { useCallback, useEffect, useReducer, useRef } from 'react';
import type { PlanPhase, PlanState, LoadingAction } from '../../types/views';
import type { BuildPlanResponse, PlanResponse } from '../../types/weekendpilot';
import {
  buildPlanStream,
  buildAlternatives,
  confirmPlan,
  executePlan,
  recoverPlan,
  patchConstraints,
  revisePlan,
} from './apiClient';
import { NODE_TYPE_LABELS } from '../../lib/constants/nodeTypes';

type Action =
  | { type: 'START_PLAN'; goal: string }
  | { type: 'STREAM_STARTED' }
  | { type: 'STREAM_TOKEN'; content: string }
  | { type: 'UPDATE_PROGRESS'; step: string }
  | { type: 'PLAN_LOADED'; result: PlanResponse }
  | { type: 'CLARIFICATION_LOADED'; result: Extract<BuildPlanResponse, { status: 'needs_clarification' }> }
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
  clarification: null,
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
  return String(action.id ?? `${action.tool ?? action.type}_${action.target ?? action.label ?? action.place_id ?? 'default'}`);
}

function isClarificationResponse(result: BuildPlanResponse): result is Extract<BuildPlanResponse, { status: 'needs_clarification' }> {
  return (result as any)?.status === 'needs_clarification';
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
        clarification: null,
        recoveredPlan: null,
        receipts: [],
        error: null,
        selectedActions: allKeys,
      };
    }
    case 'CLARIFICATION_LOADED':
      return {
        ...state,
        phase: 'clarifying',
        planId: action.result.plan_id,
        clarification: action.result,
        result: null,
        recoveredPlan: null,
        receipts: [],
        error: null,
      };
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
        clarification: null,
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
        clarification: null,
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
      if (!mountedRef.current) return;
      if (isClarificationResponse(result)) dispatch({ type: 'CLARIFICATION_LOADED', result });
      else dispatch({ type: 'PLAN_LOADED', result });
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
      const result = await executePlan(planId, Array.from(state.selectedActions));
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
    const planId = (state.recoveredPlan ?? state.result?.plan)?.id;
    if (!planId) {
      await startPlan(feedback);
      return;
    }
    try {
      const removedNodes = extractRemovedNodes(feedback, state.result);
      const result = await revisePlan(planId, {
        feedback_text: feedback,
        selected_issue_codes: inferIssueCodes(feedback),
        locked_nodes: [],
        removed_nodes: removedNodes,
        preference_updates: inferPreferenceUpdates(feedback),
        save_to_profile: true,
        user_id: 'local_demo_user',
      });
      dispatch({ type: 'CONSTRAINTS_UPDATED', result });
    } catch (err) {
      dispatch({ type: 'CONSTRAINTS_FAILED', error: err instanceof Error ? err.message : '反馈调整失败' });
    }
  }, [startPlan, state.recoveredPlan, state.result]);

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

function inferPreferenceUpdates(feedback: string): Record<string, any> {
  const updates: Record<string, any> = {};
  if (/轻松|不赶|慢|太赶/.test(feedback)) updates.pace = 'slow';
  if (/省钱|便宜|预算低|低预算/.test(feedback)) updates.budget_level = 'low';
  if (/高端|不限预算/.test(feedback)) updates.budget_level = 'high';
  if (/不想吃|不要餐厅|餐厅不想去/.test(feedback)) updates.meal_required = false;
  return updates;
}

function inferIssueCodes(feedback: string): string[] {
  const issues: string[] = [];
  if (/太赶|不赶|轻松|慢/.test(feedback)) issues.push('too_rushed');
  if (/不想吃|不要餐厅|餐厅不想去/.test(feedback)) issues.push('remove_restaurant');
  if (/省钱|便宜|预算/.test(feedback)) issues.push('cheaper');
  return issues;
}

function extractRemovedNodes(feedback: string, result: PlanResponse | null): string[] {
  if (!result || !/不想吃|不要餐厅|餐厅不想去/.test(feedback)) return [];
  return (result.plan.itinerary ?? [])
    .filter((step: any) => step.type === 'restaurant' && step.place_id)
    .map((step: any) => step.place_id);
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
