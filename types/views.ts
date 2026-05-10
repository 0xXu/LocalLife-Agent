export type ActiveTab = 'home' | 'plans' | 'activity' | 'settings';

export type PlanPhase =
  | 'idle'           // no plan, on home screen
  | 'planning'       // buildPlan in progress
  | 'results'        // plan generated, viewing itinerary
  | 'confirming'     // reviewing pending actions
  | 'executing'      // executePlan in progress
  | 'completed'      // execution done, viewing receipts
  | 'recovering';    // recoverPlan in progress

export type PlanState = {
  phase: PlanPhase;
  goal: string;
  planId: string | null;
  result: import('./weekendpilot').PlanResponse | null;
  recoveredPlan: import('./weekendpilot').PlanResponse['plan'] | null;
  receipts: import('./weekendpilot').PlanResponse['receipts'];
  error: string | null;
  selectedActions: Set<string>;
  progress: string[];
  currentStep: number;
  streamingText: string;
};
