'use client';

import { useCallback, useEffect, useReducer, useRef } from 'react';

import { approveRunActions, createRun, rejectRun, streamRunEvents } from './api';
import { initialRunState, runReducer, type RunState } from './reducer';
import type { RunEventEnvelope, RunStatus } from './schemas';

type ControllerState = RunState & {
  starting: boolean;
};

type ControllerAction =
  | { type: 'RESET' }
  | { type: 'STARTING' }
  | { type: 'STARTED'; runId: string; planId: string; status: RunStatus }
  | { type: 'EVENT'; event: RunEventEnvelope }
  | { type: 'ERROR'; error: unknown };

export type RunController = {
  state: ControllerState;
  start: (goal: string) => Promise<void>;
  approve: (actionIds: string[]) => Promise<void>;
  reject: (reason?: string) => Promise<void>;
  reset: () => void;
};

const initialControllerState: ControllerState = {
  ...initialRunState,
  starting: false,
};

export function useRunController(): RunController {
  const [state, dispatch] = useReducer(controllerReducer, initialControllerState);
  const mountedRef = useRef(true);
  const stopStreamRef = useRef<null | (() => void)>(null);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
      stopStreamRef.current?.();
    };
  }, []);

  const start = useCallback(async (goal: string) => {
    stopStreamRef.current?.();
    dispatch({ type: 'STARTING' });

    try {
      const run = await createRun({ goal, mode: 'plan' });
      if (!mountedRef.current) return;

      dispatch({
        type: 'STARTED',
        runId: run.run_id,
        planId: run.plan_id,
        status: run.status,
      });

      stopStreamRef.current = streamRunEvents(run.run_id, {
        onEvent: (event) => {
          if (mountedRef.current) {
            dispatch({ type: 'EVENT', event });
          }
        },
        onError: (error) => {
          if (mountedRef.current) {
            dispatch({ type: 'ERROR', error });
          }
        },
      });
    } catch (err) {
      if (mountedRef.current) {
        dispatch({ type: 'ERROR', error: err });
      }
    }
  }, []);

  const approve = useCallback(async (actionIds: string[]) => {
    if (!state.runId) return;
    await approveRunActions(state.runId, actionIds);
  }, [state.runId]);

  const reject = useCallback(async (reason = 'user_rejected') => {
    if (!state.runId) return;
    await rejectRun(state.runId, reason);
  }, [state.runId]);

  const reset = useCallback(() => {
    stopStreamRef.current?.();
    stopStreamRef.current = null;
    dispatch({ type: 'RESET' });
  }, []);

  return { state, start, approve, reject, reset };
}

function controllerReducer(state: ControllerState, action: ControllerAction): ControllerState {
  switch (action.type) {
    case 'RESET':
      return initialControllerState;
    case 'STARTING':
      return { ...initialControllerState, status: 'queued', starting: true };
    case 'STARTED':
      return {
        ...state,
        ...runReducer(state, {
          type: 'run.started',
          run_id: action.runId,
          plan_id: action.planId,
          seq: nextSeq(state),
          timestamp: new Date().toISOString(),
          payload: { status: action.status },
        }),
        starting: false,
      };
    case 'EVENT':
      return { ...runReducer(state, action.event), starting: false };
    case 'ERROR':
      return { ...state, status: 'failed', error: action.error, pendingActions: [], starting: false };
    default:
      return state;
  }
}

function nextSeq(state: ControllerState) {
  const lastSeq = state.events.at(-1)?.seq ?? 0;
  return lastSeq + 1;
}
