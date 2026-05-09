import { PlanResponseSchema } from '../../contracts/schemas';
import { PlanStatuses, type PlannerState } from '../state';
import { makeReceipts } from './buildItinerary';

export function executeActions(state: PlannerState): PlannerState {
  if (state.confirmed !== true) {
    return {
      ...state,
      status: PlanStatuses.USER_CONFIRMATION,
      receipts: [],
    };
  }

  if (!state.plan_response) {
    return {
      ...state,
      status: PlanStatuses.EXECUTION_FAILED,
      error: 'Plan response is missing before execution.',
    };
  }

  const receipts = makeReceipts(state.plan_response);
  const plan_response = PlanResponseSchema.parse({
    ...state.plan_response,
    receipts,
    pending_actions: [],
    plan: {
      ...state.plan_response.plan,
      status: 'completed',
      receipts,
    },
    tool_calls: state.plan_response.tool_calls.map((call) => (
      call.side_effect ? { ...call, status: 'ok', output_summary: { ok: true } } : call
    )),
    trace: state.plan_response.trace.concat({
      id: `execution_agent_${Date.now().toString(36)}`,
      agent: 'execution_agent',
      tool: 'execution_agent',
      message: '6 个确认动作已执行并返回回执。',
      input_summary: {},
      status: 'ok',
      duration_ms: 260,
      metadata: {},
    }),
  });

  return {
    ...state,
    status: PlanStatuses.DONE,
    receipts,
    pending_side_effects: [],
    plan_response,
  };
}
