import { z } from 'zod';

const JsonSchema: z.ZodType<unknown> = z.lazy(() =>
  z.union([z.string(), z.number(), z.boolean(), z.null(), z.array(JsonSchema), z.record(z.string(), JsonSchema)]),
);

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

export const RunEventEnvelopeSchema = z.object({
  type: z.string(),
  run_id: z.string(),
  plan_id: z.string().nullable().optional(),
  seq: z.number().int().min(1),
  timestamp: z.string(),
  payload: z.record(z.string(), JsonSchema).default({}),
});

export type RunStatus = z.infer<typeof RunStatusSchema>;
export type RunEventEnvelope = z.infer<typeof RunEventEnvelopeSchema>;
