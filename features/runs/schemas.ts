import { z } from 'zod';

export const RunStatusSchema = z.enum([
  'queued',
  'running',
  'needs_clarification',
  'approval_required',
  'executing',
  'completed',
  'validation_failed',
  'rejected',
  'failed',
]);

export const RunEventTypeSchema = z.enum([
  'run.started',
  'run.heartbeat',
  'agent.started',
  'agent.completed',
  'agent.handoff',
  'tool.called',
  'tool.completed',
  'tool.failed',
  'guardrail.triggered',
  'plan.draft.created',
  'plan.validation.completed',
  'approval.required',
  'actions.execution.started',
  'actions.execution.completed',
  'run.completed',
  'run.failed',
  'run.rejected',
]);

export const RunEventEnvelopeSchema = z.object({
  type: RunEventTypeSchema,
  run_id: z.string().min(1),
  plan_id: z.string().min(1).optional(),
  seq: z.number().int().positive(),
  timestamp: z.string().min(1),
  payload: z.record(z.string(), z.unknown()).default({}),
});

export const CreateRunRequestSchema = z.object({
  goal: z.string().min(1),
  user_id: z.string().min(1).default('local_demo_user'),
  mode: z.literal('plan').default('plan'),
});

export const CreateRunResponseSchema = z.object({
  run_id: z.string().min(1),
  plan_id: z.string().min(1),
  status: RunStatusSchema,
  events_url: z.string().min(1),
});

export const RunStatusResponseSchema = z.object({
  run_id: z.string().min(1),
  plan_id: z.string().min(1).optional(),
  status: RunStatusSchema,
  current_agent: z.string().nullable().optional(),
  created_at: z.string().min(1),
  updated_at: z.string().min(1),
  error: z.unknown().nullable().optional(),
});

export const ApproveActionsRequestSchema = z.object({
  action_ids: z.array(z.string().min(1)),
});

export const RejectRunRequestSchema = z.object({
  reason: z.string().min(1).default('user_rejected'),
});

export type RunStatus = z.infer<typeof RunStatusSchema>;
export type RunEventEnvelope = z.infer<typeof RunEventEnvelopeSchema>;
export type CreateRunResponse = z.infer<typeof CreateRunResponseSchema>;
export type RunStatusResponse = z.infer<typeof RunStatusResponseSchema>;
