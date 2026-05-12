import { z } from 'zod';

const JsonSchema: z.ZodType<unknown> = z.lazy(() =>
  z.union([z.string(), z.number(), z.boolean(), z.null(), z.array(JsonSchema), z.record(z.string(), JsonSchema)]),
);

export const ScenarioSchema = z.string().min(1);

export const OriginSchema = z.object({
  type: z.enum(['current_location', 'address', 'poi', 'district']),
  label: z.string(),
  lat: z.number(),
  lng: z.number(),
});

export const TimeWindowSchema = z.object({
  date: z.string(),
  start: z.string(),
  duration_hours: z.number().positive(),
  flexible: z.boolean(),
});

export const PeopleSchema = z.object({
  adults: z.number().int().nonnegative(),
  children: z.array(z.object({ age: z.number().int().nonnegative() })).default([]),
  relationship: z.string(),
});

export const PreferencesSchema = z.object({
  distance: z.string(),
  diet: z.array(z.string()).default([]),
  activity: z.array(z.string()).default([]),
  budget_level: z.string(),
}).catchall(JsonSchema);

export const ConstraintRulesSchema = z.object({
  radius_km: z.number().positive(),
  max_wait_minutes: z.number().int().nonnegative(),
  avoid: z.array(z.string()).default([]),
});

export const ParsedConstraintsSchema = z.object({
  scenario: ScenarioSchema,
  origin: OriginSchema,
  time_window: TimeWindowSchema,
  people: PeopleSchema,
  preferences: PreferencesSchema,
  constraints: ConstraintRulesSchema,
  required_actions: z.array(z.string()).default([]),
});

export const AvailabilitySlotSchema = z.object({
  time: z.string(),
  available: z.boolean(),
  capacity: z.number().int().positive().optional(),
});

export const OpenHoursSchema = z.object({
  day: z.string(),
  start: z.string(),
  end: z.string(),
});

export const PoiSchema = z.object({
  id: z.string(),
  name: z.string(),
  category: z.string(),
  lat: z.number(),
  lng: z.number(),
  distance_km: z.number().nonnegative(),
  open_hours: z.array(OpenHoursSchema),
  rating: z.number().min(0),
  review_count: z.number().int().nonnegative(),
  avg_price: z.number().nonnegative(),
  tags: z.array(z.string()).default([]),
  wait_minutes: z.number().int().nonnegative(),
  booking_supported: z.boolean(),
  availability: z.array(AvailabilitySlotSchema),
  supported_scenarios: z.array(z.string()).default([]),
  source: z.string(),
  reason: z.string(),
  risk_tags: z.array(z.string()).default([]),
  audience: z.array(z.string()).default([]),
  district: z.string(),
  menu_summary: z.string(),
  review_summary: z.string(),
});

export const ConstraintFitSchema = z.object({
  distance: z.number().min(0).max(1),
  child_friendly: z.number().min(0).max(1).optional(),
  diet: z.number().min(0).max(1).optional(),
  time: z.number().min(0).max(1),
  budget: z.number().min(0).max(1),
}).catchall(z.number().min(0).max(1));

export const ItineraryStepSchema = z.object({
  id: z.string().optional(),
  start: z.string(),
  end: z.string(),
  type: z.string(),
  title: z.string(),
  place_id: z.string().optional(),
  mode: z.string().optional(),
  travel_minutes: z.number().int().nonnegative().optional(),
  reason: z.string().optional(),
  cost: z.string().optional(),
  travel: z.string().optional(),
  score: z.number().optional(),
  risk: z.union([z.string(), z.array(z.string())]).default([]),
  poi: PoiSchema.optional(),
});

export const PlanActionSchema = z.object({
  id: z.string().optional(),
  type: z.string(),
  place_id: z.string().optional(),
  time: z.string().optional(),
  target: z.string().optional(),
  detail: z.string().optional(),
  requires_confirmation: z.boolean().default(true),
  requiresConfirmation: z.boolean().optional(),
  tool: z.string().optional(),
  label: z.string().optional(),
  payload: z.record(z.string(), JsonSchema).default({}),
});

export const ReceiptSchema = z.object({
  type: z.string(),
  tool: z.string(),
  id: z.string(),
  status: z.string(),
  detail: z.string(),
  payload: z.record(z.string(), JsonSchema).default({}),
});

export const ToolCallSchema = z.object({
  id: z.string().optional(),
  tool: z.string(),
  input_summary: z.record(z.string(), JsonSchema).default({}),
  output_summary: JsonSchema.optional(),
  status: z.enum(['ok', 'warning', 'error', 'pending', 'running', 'succeeded', 'failed', 'skipped']).default('pending'),
  duration_ms: z.number().int().nonnegative().optional(),
  side_effect: z.boolean().default(false),
  error: z.string().optional(),
});

export const TraceSpanSchema = z.object({
  span_id: z.string().optional(),
  id: z.string().optional(),
  name: z.string().optional(),
  kind: z.enum(['llm', 'tool', 'validation', 'planning', 'execution', 'recovery']).optional(),
  agent: z.string(),
  tool: z.string().optional(),
  message: z.string().optional(),
  input_summary: z.record(z.string(), JsonSchema).default({}),
  output_summary: JsonSchema.optional(),
  duration_ms: z.number().int().nonnegative().optional(),
  status: z.enum(['ok', 'warning', 'error', 'pending', 'running', 'succeeded', 'failed', 'skipped']).default('pending'),
  started_at: z.string().optional(),
  ended_at: z.string().optional(),
  summary: z.string().optional(),
  tool_call_id: z.string().optional(),
  metadata: z.record(z.string(), JsonSchema).default({}),
});

export const PendingActionSchema = z.object({
  id: z.string(),
  type: z.string(),
  tool: z.string(),
  label: z.string(),
  target: z.string().optional(),
  detail: z.string().optional(),
  requires_confirmation: z.boolean().default(true),
  requiresConfirmation: z.boolean().optional(),
  payload: z.record(z.string(), JsonSchema).default({}),
});

export const PlanOverviewSchema = z.object({
  theme: z.string(),
  totalDuration: z.string(),
  driveTime: z.string(),
  walkingDistance: z.string(),
  estimatedCost: z.string(),
  score: z.number(),
  estimated_budget_value: z.number().optional(),
});

export const PlanVariantSchema = z.object({
  id: z.string(),
  kind: z.string().optional(),
  title: z.string(),
  summary: z.string().optional(),
  score: z.number().optional(),
  estimated_budget: z.number().optional(),
  constraint_fit: ConstraintFitSchema.optional(),
  itinerary: z.array(ItineraryStepSchema).default([]),
  overview: PlanOverviewSchema.optional(),
  actions: z.array(PlanActionSchema).default([]),
});

export const CandidateSetItemSchema = z.object({
  place: z.record(z.string(), JsonSchema),
  total_score: z.number(),
  score_breakdown: z.record(z.string(), z.number()),
  explanation: z.string(),
});

export const UserPreferenceSchema = z.object({
  key: z.string(),
  value: JsonSchema,
  source: z.string(),
  confidence: z.number().min(0).max(1),
  scope: z.string(),
  evidence: z.string(),
  expires_at: z.string().default(''),
  user_editable: z.boolean().default(true),
  sensitive: z.boolean().default(false),
});

export const UserProfileSchema = z.object({
  user_id: z.string(),
  explicit_preferences: z.array(UserPreferenceSchema).default([]),
  learned_preferences: z.array(UserPreferenceSchema).default([]),
  session_preferences: z.array(UserPreferenceSchema).default([]),
});

export const PlanSchema = z.object({
  id: z.string(),
  status: z.string(),
  title: z.string(),
  summary: z.string(),
  constraint_fit: ConstraintFitSchema,
  itinerary: z.array(ItineraryStepSchema).default([]),
  overview: PlanOverviewSchema,
  actions: z.array(PlanActionSchema).default([]),
  variants: z.array(PlanVariantSchema).default([]),
  receipts: z.array(ReceiptSchema).default([]),
  badges: z.array(z.string()).default([]),
});

export const RecoveryDiffSchema = z.object({
  changed: z.string(),
  reason: z.string(),
  from: z.string().optional(),
  to: z.string().optional(),
  costDelta: z.string().optional(),
  travelDelta: z.string().optional(),
  timeDelta: z.string().optional(),
  preserved: z.array(z.string()).default([]),
  removed: z.array(z.object({
    id: z.string().optional(),
    title: z.string().optional(),
    reason: z.string(),
  })).default([]),
});

export const AdjustmentSchema = z.object({
  requested_by: z.enum(['user', 'agent', 'system']).default('agent'),
  reason: z.string(),
  changes: z.array(z.string()).default([]),
  requires_confirmation: z.boolean().default(false),
  payload: z.record(z.string(), JsonSchema).default({}),
});

export const PlanResponseSchema = z.object({
  constraints: ParsedConstraintsSchema,
  progress: z.array(z.string()).default([]),
  trace: z.array(TraceSpanSchema).default([]),
  tool_calls: z.array(ToolCallSchema).default([]),
  pending_actions: z.array(PendingActionSchema).default([]),
  candidate_sets: z.record(z.string(), z.array(CandidateSetItemSchema)).default({}),
  rejected_candidates: z.record(z.string(), z.array(z.record(z.string(), JsonSchema))).default({}),
  user_profile: UserProfileSchema.optional(),
  route: z.object({
    legs: z.array(z.object({
      from: z.string(),
      to: z.string(),
      mode: z.string(),
      duration_minutes: z.number().int().nonnegative(),
      distance_km: z.number().nonnegative(),
      route_summary: z.string().optional(),
    })).default([]),
    total_travel_minutes: z.number().int().nonnegative(),
    walking_distance_km: z.number().nonnegative(),
    drive_time_minutes: z.number().int().nonnegative(),
    polyline: z.object({
      type: z.literal('LineString'),
      coordinates: z.array(z.tuple([z.number(), z.number()])),
    }),
    provider: z.string(),
  }).optional(),
  itinerary: z.array(ItineraryStepSchema).default([]),
  plan: PlanSchema,
  actions: z.array(PlanActionSchema).default([]),
  variants: z.array(PlanVariantSchema).default([]),
  receipts: z.array(ReceiptSchema).default([]),
  diff: RecoveryDiffSchema.optional(),
  adjustment: AdjustmentSchema.optional(),
});

export const PlanRevisionResponseSchema = z.object({
  revision: z.object({
    revision_id: z.string(),
    feedback_text: z.string(),
    constraint_updates: z.record(z.string(), JsonSchema),
  }),
  diff: z.object({
    kept: z.array(z.string()).default([]),
    removed: z.array(z.record(z.string(), JsonSchema)).default([]),
    added: z.array(z.record(z.string(), JsonSchema)).default([]),
    changed_constraints: z.record(z.string(), JsonSchema).default({}),
  }),
  learned_preferences: z.array(UserPreferenceSchema).default([]),
}).passthrough();

export const ClarificationResponseSchema = z.object({
  status: z.literal('needs_clarification'),
  plan_id: z.string(),
  missing_fields: z.array(z.string()).default([]),
  clarifying_questions: z.array(z.object({
    field: z.string(),
    question: z.string(),
  })).default([]),
  trace: z.array(TraceSpanSchema).default([]),
  tool_calls: z.array(ToolCallSchema).default([]),
});
