export type ActiveTab = 'home' | 'plans' | 'activity' | 'settings';

export type PlanPhase =
  | 'idle'           // no plan, on home screen
  | 'planning'       // buildPlan in progress
  | 'clarifying'     // backend needs more information
  | 'results'        // plan generated, viewing itinerary
  | 'confirming'     // reviewing pending actions
  | 'executing'      // executePlan in progress
  | 'completed'      // execution done, viewing receipts
  | 'recovering';    // recoverPlan in progress

export type LoadingAction = 'constraints' | 'feedback' | 'replace' | 'alternatives' | null;

export type PlanState = {
  phase: PlanPhase;
  goal: string;
  planId: string | null;
  result: import('./weekendpilot').PlanResponse | null;
  clarification: import('./weekendpilot').ClarificationResponse | null;
  recoveredPlan: import('./weekendpilot').PlanResponse['plan'] | null;
  receipts: import('./weekendpilot').PlanResponse['receipts'];
  error: string | null;
  selectedActions: Set<string>;
  progress: string[];
  currentStep: number;
  streamingText: string;
  loadingAction: LoadingAction;
  loadingMessage: string;
};
