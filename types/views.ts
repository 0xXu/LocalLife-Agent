export type ActiveTab = 'home' | 'plans' | 'activity' | 'settings';

export type GraphPhase =
  | 'idle'
  | 'planning'
  | 'needs_clarification'
  | 'validation_failed'
  | 'constraints_parsed'
  | 'context_ready'
  | 'candidates_ready'
  | 'ranked'
  | 'itinerary_built'
  | 'recovering'
  | 'ready'
  | 'pending_approval'
  | 'executing'
  | 'partially_completed'
  | 'completed'
  | 'cancelled'
  | 'failed';

export type PlanPhase =
  | 'idle'           // no plan, on home screen
  | 'planning'       // buildPlan in progress
  | 'clarifying'     // backend needs more information
  | 'results'        // plan generated, viewing itinerary
  | 'executing'      // resume approval in progress
  | 'completed';     // execution done, viewing receipts

export type LoadingAction = 'approval' | null;

export type PlanState = {
  phase: PlanPhase;
  graphPhase: GraphPhase;
  goal: string;
  runId: string | null;
  threadId: string | null;
  planId: string | null;
  revisionId: string | null;
  result: import('./weekendpilot').PlanResponse | null;
  clarification: import('./weekendpilot').ClarificationResponse | null;
  receipts: import('./weekendpilot').PlanResponse['receipts'];
  error: string | null;
  selectedActions: Set<string>;
  progress: string[];
  currentStep: number;
  streamingText: string;
  loadingAction: LoadingAction;
  loadingMessage: string;
};
