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
  'run.running',
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
  'clarification.required',
  'approval.required',
  'run.executing',
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

export const ClarificationOptionSchema = z.object({
  label: z.string().min(1),
  value: z.union([z.string(), z.number(), z.boolean()]),
});

export const ClarificationQuestionSchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  description: z.string().optional(),
  kind: z.enum(['single_select', 'multi_select', 'number', 'text', 'time', 'location']),
  required: z.boolean(),
  options: z.array(ClarificationOptionSchema).optional(),
  allow_custom: z.boolean().optional(),
  validation: z.object({
    min: z.number().optional(),
    max: z.number().optional(),
    pattern: z.string().optional(),
  }).optional(),
});

export const ClarificationRequiredPayloadSchema = z.object({
  question: ClarificationQuestionSchema,
  partial_constraints: z.record(z.string(), z.unknown()).default({}),
  missing_fields: z.array(z.string()).default([]),
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

export const SubmitClarificationRequestSchema = z.object({
  question_id: z.string().min(1),
  answer: z.unknown(),
});

export type RunStatus = z.infer<typeof RunStatusSchema>;
export type RunEventEnvelope = z.infer<typeof RunEventEnvelopeSchema>;
export type ClarificationOption = z.infer<typeof ClarificationOptionSchema>;
export type ClarificationQuestion = z.infer<typeof ClarificationQuestionSchema>;
export type ClarificationRequiredPayload = z.infer<typeof ClarificationRequiredPayloadSchema>;
export type CreateRunResponse = z.infer<typeof CreateRunResponseSchema>;
export type RunStatusResponse = z.infer<typeof RunStatusResponseSchema>;
export type SubmitClarificationRequest = z.infer<typeof SubmitClarificationRequestSchema>;
