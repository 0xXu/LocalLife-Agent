export type TaskPhase =
  | 'understanding'
  | 'clarifying'
  | 'retrieving'
  | 'composing'
  | 'awaiting_mandate'
  | 'awaiting_transaction'
  | 'executing'
  | 'needs_replan'
  | 'unsupported'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type ActionKind =
  | 'reserve_table'
  | 'buy_coupon'
  | 'buy_ticket'
  | 'request_ride'
  | 'book_service'
  | 'place_order'
  | 'start_navigation'
  | 'change_reservation'
  | 'change_ticket'
  | 'change_ride'
  | 'cancel_reservation'
  | 'refund_coupon'
  | 'refund_ticket'
  | 'cancel_ride'
  | 'cancel_service'
  | 'cancel_order';

export interface Evidence {
  checked_at: string;
  detail: string;
  inventory_version: number;
  valid_for_seconds: number;
}

export interface Constraint {
  id: string;
  kind: string;
  label: string;
  value: string;
  hard: boolean;
  source: 'explicit' | 'inferred' | 'default';
}

export interface Assumption {
  id: string;
  label: string;
  value: string;
  reason: string;
  editable: boolean;
}

export interface GoalContract {
  outcome: string;
  city: string;
  origin: string;
  party_size: number;
  budget_yuan: number;
  deadline: string;
  deadline_label: string;
  context_facts: Array<{
    id: string;
    key: string;
    label: string;
    value: string;
    source: 'explicit' | 'inferred' | 'default';
  }>;
  preferences: string[];
  constraints: Constraint[];
  assumptions: Assumption[];
  open_questions: string[];
  locked_fields: string[];
}

export interface GoalEditPayload {
  outcome?: string;
  city?: string;
  origin?: string;
  party_size?: number;
  budget_yuan?: number;
  deadline?: string;
  deadline_label?: string;
  constraint_edits?: Array<{ id: string; value?: string; hard?: boolean; delete?: boolean }>;
  assumption_edits?: Array<{ id: string; value?: string; delete?: boolean }>;
  lock_fields?: string[];
  unlock_fields?: string[];
}

export type PlanEditOperation =
  | 'lock_node'
  | 'unlock_node'
  | 'replace_node'
  | 'remove_node'
  | 'adjust_node'
  | 'adjust_budget'
  | 'select_alternative'
  | 'undo_last_edit';

export interface PlanEditPayload {
  instruction: string;
  operation: PlanEditOperation;
  node_id?: string;
  keep_other_nodes?: boolean;
  starts_at?: string;
  budget_yuan?: number;
  option_id?: string;
  candidate_id?: string;
}

export interface PlanNode {
  id: string;
  capability_id: string;
  vertical: 'food' | 'activity' | 'service' | 'delivery' | 'mobility';
  title: string;
  option_id: string;
  starts_at: string;
  ends_at: string;
  price_yuan: number;
  venue: string;
  reason: string;
  consumes_user_time: boolean;
  trigger_kind: 'inventory_unavailable' | 'queue_delay' | 'price_increase' | 'eta_delay' | 'hold_expired' | 'weather_change' | 'user_late' | 'location_change' | 'fulfillment_failure';
  actions: ActionKind[];
  status: 'proposed' | 'approved' | 'executing' | 'completed' | 'failed' | 'compensated';
  depends_on: string[];
  alternatives: string[];
  evidence: Evidence;
  supply_reference: {
    id: string;
    supply_id: string;
    stage: 'verified' | 'quoted' | 'held' | 'committed' | 'changed' | 'cancelled' | 'refunded' | 'expired';
    quote_id: string | null;
    hold_id: string | null;
    commitment_id: string | null;
    commitments: Partial<Record<ActionKind, string>>;
    quoted_total_yuan: number | null;
    hold_expires_at: string | null;
    terms: string[];
  } | null;
}

export interface PlanAlternative {
  candidate_id: string;
  direction: 'cheaper' | 'earlier' | 'less_elapsed' | 'less_movement' | 'stronger_experience';
  summary: string;
  total_yuan: number;
  completion_time: string;
  option_ids: string[];
}

export interface FallbackPolicy {
  id: string;
  node_id: string;
  replacement: PlanNode;
  affected_node_ids: string[];
  authorization_effect: 'within_mandate' | 'confirmation_required';
}

export interface DecisionPoint {
  id: string;
  node_id: string;
  trigger: {
    kind: 'inventory_unavailable' | 'queue_delay' | 'price_increase' | 'eta_delay' | 'hold_expired' | 'weather_change' | 'user_late' | 'location_change' | 'fulfillment_failure';
    node_id: string;
    threshold: number;
  };
  slack_minutes: number;
  decision_deadline: string;
  fallbacks: FallbackPolicy[];
}

export interface PlanPolicy {
  primary_plan: PlanGraph;
  alternatives: PlanAlternative[];
  decision_points: DecisionPoint[];
}

export interface PlanGraph {
  version: number;
  title: string;
  thesis: string;
  goal: GoalContract;
  nodes: PlanNode[];
  total_yuan: number;
  rationale: string[];
  tradeoffs: string[];
  locked_node_ids: string[];
  mandate: {
    max_total_yuan: number;
    deadline: string;
    allowed_verticals: string[];
    max_price_increase_yuan: number;
    allow_auto_substitution: boolean;
    approved_at: string | null;
  };
  updated_at: string;
}

export interface ClarificationQuestion {
  id: string;
  prompt: string;
  why_now: string;
  options: Array<{
    id: string;
    label: string;
    impact: string;
    branch: {
      action: 'continue' | 'stop';
      goal: GoalContract;
      capability_ids: string[];
      temporal_constraints: Array<{
        capability_id: string;
        relation: 'exact_start' | 'earliest_start' | 'latest_end';
        time: string;
        source_constraint_id: string | null;
      }>;
      path: 'quick' | 'orchestrated';
      context_scope: string;
      feasibility_status: 'feasible' | 'infeasible' | 'unknown';
      verified_candidate_ids: Record<string, string[]>;
      authorization_effect: 'unchanged' | 'confirmation_required';
    } | null;
  }>;
  allow_free_text: boolean;
}

export interface ToolTrace {
  id: string;
  agent: string;
  tool: string;
  input_summary: Record<string, unknown>;
  status: 'succeeded' | 'failed';
  result_summary: string;
  world_version: number | null;
  duration_ms: number;
  occurred_at: string;
}

export interface TaskProgressEvent {
  id: string;
  kind: 'goal_understood' | 'retrieval_started' | 'retrieval_completed' | 'feasibility_conflict' | 'composing_plan' | 'patch_completed';
  detail: string;
  revision: number;
  capability_id: string | null;
  occurred_at: string;
}

export interface FulfillmentEvent {
  id: string;
  task_id: string;
  node_id: string;
  action: ActionKind;
  status: 'started' | 'succeeded' | 'failed' | 'compensated';
  detail: string;
  receipt_id: string | null;
  actual_amount_yuan: number | null;
  lifecycle_stage: string | null;
  compensation_action: ActionKind | null;
  occurred_at: string;
}

export interface SupplySignal {
  id: string;
  supply_id: string;
  kind: 'inventory_unavailable' | 'queue_delay' | 'price_increase' | 'eta_delay' | 'hold_expired' | 'weather_change' | 'user_late' | 'location_change' | 'fulfillment_failure';
  detail: string;
  world_version: number;
  magnitude: number;
  observed_at: string;
}

export type RealityEventKind = SupplySignal['kind'] | 'node_completed';

export interface LiveState {
  next_step: {
    node_id: string;
    title: string;
    instruction: string;
    due_at: string;
    status: 'upcoming' | 'ready' | 'in_progress' | 'done' | 'blocked';
    completion_available: boolean;
    completion_hint: string | null;
  } | null;
  risk: string | null;
  affected_node_ids: string[];
  agent_activity: string;
  waiting_for: string | null;
  available_actions: ActionKind[];
  last_signal: SupplySignal | null;
  actual_outcome: {
    total_yuan: number;
    completed_node_ids: string[];
    compensated_node_ids: string[];
    completed_at: string;
    summary: string;
    goal_attainment: 'unknown' | 'achieved' | 'partly' | 'not_achieved';
  } | null;
  updated_at: string;
}

export interface PreferenceFact {
  id: string;
  user_id: string;
  subject: string;
  context_scope: string;
  dimension: string;
  preference: string;
  polarity: 'prefer' | 'avoid' | 'require';
  source: string;
  confidence: number;
  observed_at: string;
  active: boolean;
}

export interface TransactionConfirmation {
  lines: Array<{
    node_id: string;
    action: ActionKind;
    label: string;
    amount_yuan: number;
  }>;
  total_cap_yuan: number;
  confirmed_at: string | null;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'agent' | 'system';
  content: string;
  created_at: string;
}

export interface TaskSnapshot {
  id: string;
  user_id: string;
  goal_text: string;
  phase: TaskPhase;
  revision: number;
  messages: ChatMessage[];
  goal: GoalContract | null;
  question: ClarificationQuestion | null;
  policy: PlanPolicy | null;
  feasible_plan_set: {
    status: 'feasible' | 'infeasible' | 'unknown';
    pareto_candidate_ids: string[];
    infeasible_reasons: Array<{ code: string; message: string }>;
  } | null;
  last_patch: {
    from_version: number;
    to_version: number;
    summary: string;
    operations: Array<{
      operation: 'add' | 'replace' | 'remove' | 'update';
      node_id: string;
      reason: string;
      node: PlanNode | null;
    }>;
    requires_confirmation: boolean;
    trigger_source: 'goal_edit' | 'plan_edit' | 'supply_event' | 'policy_trigger';
    authorization_effect: 'within_mandate' | 'confirmation_required';
  } | null;
  pending_plan_edit: {
    source: 'natural_language' | 'direct';
    instruction: string;
    operation: PlanEditOperation | null;
    node_id: string | null;
    keep_other_nodes: boolean;
    starts_at: string | null;
    budget_yuan: number | null;
    option_id: string | null;
    candidate_id: string | null;
  } | null;
  plan_undo: { fulfillment_event_count: number } | null;
  transaction_confirmation: TransactionConfirmation | null;
  fulfillment_events: FulfillmentEvent[];
  tool_traces: ToolTrace[];
  progress_events: TaskProgressEvent[];
  workflow_id: string | null;
  observation_workflow_id: string | null;
  context_scope: string;
  intent_path: 'quick' | 'orchestrated' | null;
  applied_preference_fact_ids: string[];
  supply_signals: SupplySignal[];
  reality_events: Array<{
    id: string;
    task_id: string;
    kind: RealityEventKind;
    detail: string;
    magnitude: number;
    node_id: string | null;
    supply_id: string | null;
    location: string | null;
    occurred_at: string;
  }>;
  live: LiveState | null;
  outcome_check_in: {
    prompt: string;
    response: 'achieved' | 'partly' | 'not_achieved' | null;
    note: string | null;
    responded_at: string | null;
  } | null;
  created_at: string;
  updated_at: string;
}
