import { sideEffectTool } from './common';

export const sendPlanMessageTool = sideEffectTool('send_plan_message', 'MSG', (input) => ({
  message_id: input.message_id ?? 'message_seed',
  to: input.to ?? 'family',
  content: input.content ?? '',
}));
