import type { z } from 'zod';
import type {
  AdjustmentSchema,
  AvailabilitySlotSchema,
  ConstraintFitSchema,
  ConstraintRulesSchema,
  ItineraryStepSchema,
  OpenHoursSchema,
  OriginSchema,
  ParsedConstraintsSchema,
  PendingActionSchema,
  PeopleSchema,
  PlanActionSchema,
  PlanOverviewSchema,
  PlanResponseSchema,
  PlanRevisionResponseSchema,
  PlanSchema,
  PlanVariantSchema,
  PoiSchema,
  PreferencesSchema,
  ReceiptSchema,
  RecoveryDiffSchema,
  ScenarioSchema,
  TimeWindowSchema,
  ToolCallSchema,
  TraceSpanSchema,
  ClarificationResponseSchema,
} from '../lib/contracts/schemas';

export type Scenario = z.infer<typeof ScenarioSchema>;
export type Origin = z.infer<typeof OriginSchema>;
export type TimeWindow = z.infer<typeof TimeWindowSchema>;
export type People = z.infer<typeof PeopleSchema>;
export type Preferences = z.infer<typeof PreferencesSchema>;
export type ConstraintRules = z.infer<typeof ConstraintRulesSchema>;
export type ParsedConstraints = z.infer<typeof ParsedConstraintsSchema>;
export type AvailabilitySlot = z.infer<typeof AvailabilitySlotSchema>;
export type OpenHours = z.infer<typeof OpenHoursSchema>;
export type Poi = z.infer<typeof PoiSchema>;
export type ConstraintFit = z.infer<typeof ConstraintFitSchema>;
export type ItineraryStep = z.infer<typeof ItineraryStepSchema>;
export type PlanAction = z.infer<typeof PlanActionSchema>;
export type Receipt = z.infer<typeof ReceiptSchema>;
export type ToolCall = z.infer<typeof ToolCallSchema>;
export type TraceSpan = z.infer<typeof TraceSpanSchema>;
export type PendingAction = z.infer<typeof PendingActionSchema>;
export type PlanOverview = z.infer<typeof PlanOverviewSchema>;
export type PlanVariant = z.infer<typeof PlanVariantSchema>;
export type Plan = z.infer<typeof PlanSchema>;
export type RecoveryDiff = z.infer<typeof RecoveryDiffSchema>;
export type Adjustment = z.infer<typeof AdjustmentSchema>;
export type PlanResponse = z.infer<typeof PlanResponseSchema>;
export type PlanRevisionResponse = z.infer<typeof PlanRevisionResponseSchema>;
export type ClarificationResponse = z.infer<typeof ClarificationResponseSchema>;
export type BuildPlanResponse = PlanResponse | ClarificationResponse;

export type PlanStatus =
  | 'draft'
  | 'pending_confirmation'
  | 'confirmed'
  | 'executing'
  | 'completed'
  | 'recovering'
  | 'failed';
