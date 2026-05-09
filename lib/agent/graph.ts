import { randomUUID } from 'node:crypto';

import { buildContext } from './nodes/buildContext';
import { buildItinerary } from './nodes/buildItinerary';
import { executeActions } from './nodes/executeActions';
import { parseConstraintsNode } from './nodes/parseConstraints';
import { rankCandidates } from './nodes/rankCandidates';
import { searchCandidates } from './nodes/searchCandidates';
import { validatePlan } from './nodes/validatePlan';
import { waitForConfirmation } from './nodes/waitForConfirmation';
import {
  createInitialState,
  PlanStatuses,
  type PlannerCheckpointer,
  type PlannerInput,
  type PlannerRunnableConfig,
  type PlannerState,
} from './state';

export function createTestCheckpointer(): PlannerCheckpointer {
  const checkpoints = new Map<string, PlannerState>();

  return {
    get(threadId: string) {
      return clone(checkpoints.get(threadId));
    },
    put(threadId: string, state: PlannerState) {
      checkpoints.set(threadId, clone(state));
    },
  };
}

export function createPlannerGraph({ checkpointer = createTestCheckpointer() }: { checkpointer?: PlannerCheckpointer } = {}) {
  return {
    async invoke(input: PlannerInput, config: PlannerRunnableConfig = {}) {
      const threadId = config.configurable?.thread_id ?? randomUUID();
      const previous = await checkpointer.get(threadId);

      if (input.confirmed === true) {
        const state = await resumeWithConfirmation(threadId, previous, input);
        await checkpointer.put(threadId, state);
        return state;
      }

      const initial = createInitialState(threadId, input);
      let state = await parseConstraintsNode(initial);
      await checkpointer.put(threadId, state);
      if (state.status === PlanStatuses.NEED_CLARIFICATION) {
        return state;
      }

      state = buildContext(state);
      await checkpointer.put(threadId, state);
      state = await searchCandidates(state);
      await checkpointer.put(threadId, state);
      state = rankCandidates(state);
      await checkpointer.put(threadId, state);
      state = buildItinerary(state);
      await checkpointer.put(threadId, state);
      state = validatePlan(state);
      await checkpointer.put(threadId, state);
      state = waitForConfirmation(state);

      await checkpointer.put(threadId, state);
      return state;
    },
  };
}

async function resumeWithConfirmation(threadId: string, previous: PlannerState | undefined, input: PlannerInput) {
  const state = previous ?? createInitialState(threadId, input);
  const executableState: PlannerState = {
    ...state,
    thread_id: threadId,
    confirmed: true,
    plan_response: input.plan_response ?? state.plan_response,
    status: PlanStatuses.EXECUTE_ACTIONS,
  };

  return executeActions(executableState);
}

function clone<T>(value: T): T {
  return value === undefined ? value : JSON.parse(JSON.stringify(value));
}
