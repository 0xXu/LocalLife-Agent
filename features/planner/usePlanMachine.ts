import { useCallback, useEffect, useReducer, useRef } from 'react';
import type { GraphPhase, PlanPhase, PlanState } from '../../types/views';
import type { ClarificationResponse, GraphRunEvent, GraphRunStartResponse, PlanResponse } from '../../types/weekendpilot';
import { getPlan, rejectPlan, resumePlan, startPlanRun, streamRunUpdates } from './apiClient';

type Action =
  | { type: 'START_PLAN'; goal: string }
  | { type: 'RUN_STARTED'; run: GraphRunStartResponse }
  | { type: 'GRAPH_UPDATED'; event: GraphRunEvent }
  | { type: 'UPDATE_PROGRESS'; step: string }
  | { type: 'PLAN_LOADED'; result: PlanResponse }
  | { type: 'CLARIFICATION_LOADED'; result: ClarificationResponse }
  | { type: 'PLAN_FAILED'; error: string }
  | { type: 'START_EXECUTE' }
  | { type: 'EXECUTE_LOADED'; result: PlanResponse }
  | { type: 'EXECUTE_FAILED'; error: string }
  | { type: 'SET_LOADING'; message: string }
  | { type: 'CLEAR_LOADING' }
  | { type: 'TOGGLE_ACTION'; key: string }
  | { type: 'SELECT_ALL_ACTIONS' }
  | { type: 'DESELECT_ALL_ACTIONS' }
  | { type: 'RESET' }
  | { type: 'SET_PHASE'; phase: PlanPhase };

const initialState: PlanState = {
  phase: 'idle',
  graphPhase: 'idle',
  goal: '',
  runId: null,
  threadId: null,
  planId: null,
  revisionId: null,
  result: null,
  clarification: null,
  receipts: [],
  error: null,
  selectedActions: new Set(),
  progress: [],
  currentStep: -1,
  streamingText: '',
  loadingAction: null,
  loadingMessage: '',
};

export function getActionKey(action: Record<string, unknown>): string {
  return String(action.action_id ?? action.id ?? `${action.tool ?? action.type}_${action.target ?? action.label ?? action.place_id ?? 'default'}`);
}

const PHASE_TO_STEP: Record<string, number> = {
  constraints_parsed: 0,    // step 0 done, step 1 running
  context_ready: 1,         // step 1 done, step 2 running
  candidates_ready: 2,      // step 2 done, step 3 running
  ranked: 3,                // step 3 done, step 4 running
  itinerary_built: 4,       // step 4 done, step 5 running
  pending_confirmation: 5,  // all done
  needs_clarification: -1,  // special path
  recovering: 5,            // retry - step 5 running
};

function graphPhaseOf(result: PlanResponse): GraphPhase {
  return String(result.revision?.phase ?? result.plan.status ?? 'idle') as GraphPhase;
}

function planPhaseOf(result: PlanResponse): PlanPhase {
  const phase = graphPhaseOf(result);
  if (phase === 'completed') return 'completed';
  if (phase === 'needs_clarification') return 'clarifying';
  return 'results';
}

function actionsFor(result: PlanResponse | null): Array<Record<string, unknown>> {
  if (!result) return [];
  const topLevel = (result.actions ?? []) as Array<Record<string, unknown>>;
  return topLevel.length ? topLevel : ((result.plan.actions ?? []) as Array<Record<string, unknown>>);
}

function selectableActions(result: PlanResponse | null): Array<Record<string, unknown>> {
  return actionsFor(result).filter((action) => String(action.status ?? 'pending') === 'pending');
}

function clarificationFromPlanResponse(result: PlanResponse): ClarificationResponse {
  const plan = result.plan as Record<string, any>;
  return {
    status: 'needs_clarification',
    plan_id: result.plan_id ?? result.plan.id,
    missing_fields: Array.isArray(plan.missing_fields) ? plan.missing_fields : [],
    clarifying_questions: Array.isArray(plan.clarifying_questions) ? plan.clarifying_questions : [],
    trace: result.trace ?? [],
    tool_calls: result.tool_calls ?? [],
  };
}

function reducer(state: PlanState, action: Action): PlanState {
  switch (action.type) {
    case 'START_PLAN':
      return { ...initialState, phase: 'planning', graphPhase: 'planning', goal: action.goal, currentStep: 0, progress: ['Graph run starting'] };
    case 'RUN_STARTED':
      return {
        ...state,
        runId: action.run.run_id,
        threadId: action.run.thread_id,
        planId: action.run.plan_id,
        progress: [...state.progress, 'Graph run created'],
        currentStep: Math.max(state.currentStep + 1, 1),
      };
    case 'GRAPH_UPDATED': {
      const mappedStep = PHASE_TO_STEP[action.event.phase] ?? state.currentStep;
      const newStep = mappedStep >= 0 ? mappedStep + 1 : state.currentStep;
      return {
        ...state,
        graphPhase: action.event.phase as GraphPhase,
        revisionId: action.event.revision_id,
        progress: [...state.progress, `Graph phase: ${action.event.phase}`],
        currentStep: newStep,
        streamingText: action.event.step_detail ?? state.streamingText,
      };
    }
    case 'UPDATE_PROGRESS':
      return {
        ...state,
        progress: [...state.progress, action.step],
        currentStep: state.currentStep + 1,
      };
    case 'PLAN_LOADED': {
      const pending = selectableActions(action.result);
      return {
        ...state,
        phase: planPhaseOf(action.result),
        graphPhase: graphPhaseOf(action.result),
        planId: action.result.plan_id ?? action.result.plan.id,
        revisionId: action.result.revision?.revision_id ?? state.revisionId,
        result: action.result,
        clarification: graphPhaseOf(action.result) === 'needs_clarification' ? clarificationFromPlanResponse(action.result) : null,
        receipts: action.result.receipts ?? [],
        selectedActions: new Set(pending.map(getActionKey)),
        error: null,
        loadingAction: null,
        loadingMessage: '',
        currentStep: 6,
      };
    }
    case 'CLARIFICATION_LOADED':
      return {
        ...state,
        phase: 'clarifying',
        graphPhase: 'needs_clarification',
        planId: action.result.plan_id,
        clarification: action.result,
        result: null,
        receipts: [],
        error: null,
      };
    case 'PLAN_FAILED':
      return { ...state, phase: 'idle', graphPhase: 'failed', error: action.error, loadingAction: null, loadingMessage: '' };
    case 'START_EXECUTE':
      return { ...state, phase: 'executing', graphPhase: 'executing', error: null };
    case 'EXECUTE_LOADED': {
      const pending = selectableActions(action.result);
      return {
        ...state,
        phase: planPhaseOf(action.result),
        graphPhase: graphPhaseOf(action.result),
        result: action.result,
        planId: action.result.plan_id ?? action.result.plan.id,
        revisionId: action.result.revision?.revision_id ?? state.revisionId,
        receipts: action.result.receipts ?? [],
        selectedActions: new Set(pending.map(getActionKey)),
        error: null,
        loadingAction: null,
        loadingMessage: '',
      };
    }
    case 'EXECUTE_FAILED':
      return { ...state, phase: state.result ? 'results' : 'idle', graphPhase: graphPhaseOf(state.result ?? ({ plan: { status: 'failed' } } as PlanResponse)), error: action.error, loadingAction: null, loadingMessage: '' };
    case 'SET_LOADING':
      return { ...state, loadingAction: 'approval', loadingMessage: action.message };
    case 'CLEAR_LOADING':
      return { ...state, loadingAction: null, loadingMessage: '' };
    case 'TOGGLE_ACTION': {
      const next = new Set(state.selectedActions);
      if (next.has(action.key)) next.delete(action.key);
      else next.add(action.key);
      return { ...state, selectedActions: next };
    }
    case 'SELECT_ALL_ACTIONS':
      return { ...state, selectedActions: new Set(selectableActions(state.result).map(getActionKey)) };
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
  const stopStreamRef = useRef<null | (() => void)>(null);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
      stopStreamRef.current?.();
    };
  }, []);

  const startPlan = useCallback(async (goal: string) => {
    stopStreamRef.current?.();
    dispatch({ type: 'START_PLAN', goal });
    try {
      const run = await startPlanRun(goal);
      if (!mountedRef.current) return;
      dispatch({ type: 'RUN_STARTED', run });

      if (typeof EventSource !== 'undefined') {
        stopStreamRef.current = streamRunUpdates(run.run_id, {
          onGraphUpdate: (event) => {
            if (mountedRef.current) dispatch({ type: 'GRAPH_UPDATED', event });
          },
          onError: (error) => {
            if (mountedRef.current) dispatch({ type: 'UPDATE_PROGRESS', step: error.message });
          },
        });
      }

      const result = await getPlan(run.plan_id);
      if (!mountedRef.current) return;
      dispatch({ type: 'PLAN_LOADED', result });
    } catch (err) {
      if (mountedRef.current) dispatch({ type: 'PLAN_FAILED', error: err instanceof Error ? err.message : '计划生成失败' });
    }
  }, []);

  const approveSelectedActions = useCallback(async () => {
    const planId = state.planId ?? state.result?.plan.id;
    if (!planId) return;
    const selected = Array.from(state.selectedActions);
    if (!selected.length) {
      dispatch({ type: 'EXECUTE_FAILED', error: '请选择至少一项待执行动作' });
      return;
    }

    dispatch({ type: 'START_EXECUTE' });
    try {
      const result = await resumePlan(planId, selected);
      dispatch({ type: 'EXECUTE_LOADED', result });
    } catch (err) {
      dispatch({ type: 'EXECUTE_FAILED', error: err instanceof Error ? err.message : '执行失败' });
    }
  }, [state.planId, state.result, state.selectedActions]);

  const rejectCurrentPlan = useCallback(async () => {
    const planId = state.planId ?? state.result?.plan.id;
    if (!planId) return;
    dispatch({ type: 'SET_LOADING', message: '正在取消当前计划...' });
    try {
      const result = await rejectPlan(planId);
      dispatch({ type: 'PLAN_LOADED', result });
    } catch (err) {
      dispatch({ type: 'PLAN_FAILED', error: err instanceof Error ? err.message : '取消失败' });
    }
  }, [state.planId, state.result]);

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
    stopStreamRef.current?.();
    dispatch({ type: 'RESET' });
  }, []);

  const setPhase = useCallback((phase: PlanPhase) => {
    dispatch({ type: 'SET_PHASE', phase });
  }, []);

  return {
    state,
    startPlan,
    approveSelectedActions,
    rejectCurrentPlan,
    toggleAction,
    selectAllActions,
    deselectAllActions,
    reset,
    setPhase,
    getActionKey,
  };
}
