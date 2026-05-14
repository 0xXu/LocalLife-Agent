# Frontend Graph Run Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the frontend interaction model around the backend graph-run workflow contract, with a macOS-like planner workbench while preserving the current WeekendPilot light theme.

**Architecture:** The frontend must stop calling legacy linear endpoints and treat the backend as a durable graph workflow: start a run, observe graph updates, load the persisted plan, approve/reject selected ledger actions through `resume`, and display resulting receipts. UI shifts from a linear "generate -> edit -> alternatives -> confirm -> execute" flow to a three-pane Mac workbench: plan canvas, graph/status rail, and action ledger inspector.

**Tech Stack:** Next.js 15, React 19, TypeScript, Zod contract schemas, lucide-react icons, FastAPI backend graph-run API.

---

## Backend Contract Source Of Truth

Use only the current backend API:

- `POST /api/plans/runs` with `{ goal, user_id }` returns `{ run_id, thread_id, plan_id }`.
- `GET /api/plans/runs/{run_id}/stream` returns SSE events named `graph_update`.
- `GET /api/plans/{plan_id}` returns `PlanResponse` with `revision.phase`, `plan.status`, `actions`, `pending_actions`, `receipts`.
- `POST /api/plans/{plan_id}/resume` accepts `{ decision: "approve", selected_action_ids: string[] }` or `{ decision: "reject" }`.
- `GET /api/plans` lists persisted workflow plans in `pending_approval` or `partially_completed`.
- `GET /api/plans/{plan_id}/versions` is read-only inspection.

Remove frontend usage of:

- `/api/plans/build`
- `/api/plans/build/stream`
- `/api/plans/{plan_id}/constraints`
- `/api/plans/{plan_id}/alternatives`
- `/api/plans/{plan_id}/confirm`
- `/api/plans/{plan_id}/execute`
- `/api/plans/{plan_id}/recover`
- `/api/plans/{plan_id}/revise`

## Interaction Redesign

### Core Product Model

The user should experience WeekendPilot as a "local-life operations cockpit":

- **Run:** Start a graph run from natural language.
- **Review:** See the plan, evidence, validation state, and pending side-effect actions.
- **Approve:** Select durable `action_id` items from the ledger and approve execution.
- **Continue:** If only some actions execute, the plan remains `partially_completed` and the ledger shows remaining pending actions.
- **Audit:** Receipts and versions are visible as execution proof.

### macOS Interaction Pattern, Current Theme Preserved

Keep current light palette and variables in `app/globals.css`: `--bg`, `--panel`, `--sidebar`, `--surface`, `--text`, `--muted`, `--blue`, `--violet`, `--green`, `--coral`.

Change layout behavior:

- Desktop: fixed app sidebar remains; planner content becomes a Mac-like split workspace.
- Main canvas: itinerary, overview, map, candidate evidence.
- Right inspector: action ledger and approval controls.
- Bottom/status rail: graph run stage, revision id, phase, validation status.
- Modal/sheet behavior: approvals are a compact inspector, not a full-screen wizard.
- Mobile: inspector collapses below the plan as a sticky execution panel.

Do not create a landing page. The first screen remains the usable planning interface.

---

## File Structure

### Contract and API Layer

- Modify: `lib/contracts/schemas.ts`
  - Accept backend durable fields: `action_id`, `revision`, `phase`, receipt `action_id`.
  - Add graph run response/event schemas.
- Modify: `types/weekendpilot.ts`
  - Export `GraphRunStartResponse`, `GraphRunEvent`, `ResumeDecision`.
- Modify: `types/views.ts`
  - Replace old frontend-only status assumptions with backend graph phases.
- Modify: `features/planner/apiClient.ts`
  - Remove legacy functions.
  - Add `startPlanRun`, `streamRunUpdates`, `resumePlan`, `rejectPlan`, `getPlanVersions`.
  - Keep `buildPlanStream` only as a graph-run-backed compatibility wrapper inside the frontend until `usePlanMachine` is migrated.

### Planner State

- Modify: `features/planner/usePlanMachine.ts`
  - State machine owns `runId`, `threadId`, `phase`, `revisionId`, `selectedActions`.
  - Start flow uses `POST /runs`, then stream/get plan.
  - Execute flow uses `POST /resume`.
  - Remove calls to constraints, alternatives, recover, revise, confirm, execute.
- Modify: `features/planner/usePlans.ts`
  - Saved plan execution fetches current plan and resumes selected pending actions.

### UI Components

- Create: `components/plan/GraphRunStatusRail.tsx`
  - Shows graph phase, run id, revision id, validation state.
- Create: `components/plan/ActionLedgerPanel.tsx`
  - Shows durable actions keyed by `action_id`, status, selected toggle, approve/reject controls.
- Create: `components/plan/WorkbenchTabs.tsx`
  - Segmented control for `Plan`, `Evidence`, `Trace`.
- Modify: `components/plan/PlanResultsView.tsx`
  - Convert to split workbench.
  - Remove old unsupported interaction controls.
  - Embed `ActionLedgerPanel`.
- Modify: `components/confirm/ConfirmView.tsx`
  - Either delete after migration or leave unused until cleanup task; approval should live in the inspector.
- Modify: `components/receipts/ReceiptsView.tsx`
  - Support receipt status from backend (`succeeded`, `failed`, `ok`, `success`) and show `action_id`.
- Modify: `app/page.tsx`
  - Remove separate `confirming` page flow if approval inspector replaces it.

### Styling

- Modify: `app/globals.css`
  - Add `.graph-workbench`, `.graph-workbench-main`, `.graph-workbench-inspector`, `.graph-status-rail`, `.action-ledger-panel`, `.workbench-tabs`.
  - Keep current theme variables; avoid a new color theme.

### Tests

- Modify: `tests/frontend/planner-api-client.test.tsx`
  - Assert graph-run endpoints only.
- Modify: `tests/frontend/interactive-components.test.tsx`
  - Saved plans must call `GET /api/plans/{plan_id}` then `POST /resume`.
- Create: `tests/frontend/action-ledger-panel.test.tsx`
  - Verify action selection uses `action_id`.
- Modify: any frontend test importing removed API functions.

---

## Task 1: Update Contract Schemas For Graph Run

**Files:**
- Modify: `lib/contracts/schemas.ts`
- Modify: `types/weekendpilot.ts`
- Test: `tests/contracts/*.test.ts`

- [ ] **Step 1: Write failing contract expectations**

Add a test fixture that includes backend fields currently missing from the Zod contract:

```ts
const graphPlanPayload = {
  plan_id: 'plan_test_001',
  revision: {
    revision_id: 'rev_test_001',
    phase: 'pending_approval',
    version: 1,
    goal: 'family lunch',
    constraints: {
      scenario: 'family',
      origin: { type: 'district', label: 'home', lat: 31.2, lng: 121.5 },
      time_window: { date: '2026-05-14', start: '14:00', duration_hours: 4, flexible: true },
      people: { adults: 2, children: [{ age: 5 }], relationship: 'family' },
      preferences: { distance: 'nearby', diet: [], activity: [], budget_level: 'medium' },
      constraints: { radius_km: 5, max_wait_minutes: 15, avoid: [] },
      required_actions: ['send_plan_message'],
    },
    plan: {
      id: 'plan_test_001',
      status: 'pending_approval',
      title: '亲子半日计划',
      summary: '轻松安排',
      constraint_fit: { distance: 1, time: 1, budget: 1 },
      itinerary: [],
      overview: {
        theme: '家庭',
        totalDuration: '4 小时',
        driveTime: '约 20 分钟',
        walkingDistance: '1 公里',
        estimatedCost: '¥300',
        score: 88,
      },
      actions: [{
        action_id: 'act_msg_001',
        type: 'send_plan_message',
        tool: 'messaging',
        label: '发送计划',
        detail: '发送给同行人',
        status: 'pending',
        payload: {},
        requires_confirmation: true,
      }],
      receipts: [],
      badges: ['家庭'],
    },
  },
  plan: {
    id: 'plan_test_001',
    status: 'pending_approval',
    title: '亲子半日计划',
    summary: '轻松安排',
    constraint_fit: { distance: 1, time: 1, budget: 1 },
    itinerary: [],
    overview: {
      theme: '家庭',
      totalDuration: '4 小时',
      driveTime: '约 20 分钟',
      walkingDistance: '1 公里',
      estimatedCost: '¥300',
      score: 88,
    },
    actions: [{
      action_id: 'act_msg_001',
      type: 'send_plan_message',
      tool: 'messaging',
      label: '发送计划',
      detail: '发送给同行人',
      status: 'pending',
      payload: {},
      requires_confirmation: true,
    }],
    receipts: [],
    badges: ['家庭'],
  },
  actions: [{
    action_id: 'act_msg_001',
    type: 'send_plan_message',
    tool: 'messaging',
    label: '发送计划',
    detail: '发送给同行人',
    status: 'pending',
    payload: {},
    requires_confirmation: true,
  }],
  pending_actions: [{
    action_id: 'act_msg_001',
    type: 'send_plan_message',
    tool: 'messaging',
    label: '发送计划',
    detail: '发送给同行人',
    status: 'pending',
    payload: {},
    requires_confirmation: true,
  }],
  receipts: [],
  constraints: {
    scenario: 'family',
    origin: { type: 'district', label: 'home', lat: 31.2, lng: 121.5 },
    time_window: { date: '2026-05-14', start: '14:00', duration_hours: 4, flexible: true },
    people: { adults: 2, children: [{ age: 5 }], relationship: 'family' },
    preferences: { distance: 'nearby', diet: [], activity: [], budget_level: 'medium' },
    constraints: { radius_km: 5, max_wait_minutes: 15, avoid: [] },
    required_actions: ['send_plan_message'],
  },
};
```

- [ ] **Step 2: Run contract tests and confirm failure**

Run:

```bash
npm run test:contracts
```

Expected: failure because `action_id`, action `status`, and top-level `revision` are not fully modeled.

- [ ] **Step 3: Update schemas**

Change `PlanActionSchema` and `PendingActionSchema` to include durable backend fields:

```ts
export const PlanActionSchema = z.object({
  id: z.string().optional(),
  action_id: z.string().optional(),
  type: z.string(),
  place_id: z.string().optional(),
  time: z.string().optional(),
  target: z.string().optional(),
  detail: z.string().optional(),
  status: z.enum(['pending', 'executing', 'succeeded', 'failed', 'skipped']).optional(),
  requires_confirmation: z.boolean().default(true),
  requiresConfirmation: z.boolean().optional(),
  tool: z.string().optional(),
  label: z.string().optional(),
  payload: z.record(z.string(), JsonSchema).default({}),
  idempotency_key: z.string().optional(),
});

export const PendingActionSchema = PlanActionSchema.extend({
  action_id: z.string(),
  tool: z.string(),
  label: z.string(),
});
```

Add graph run schemas:

```ts
export const GraphRunStartResponseSchema = z.object({
  run_id: z.string(),
  thread_id: z.string(),
  plan_id: z.string(),
});

export const PlanRevisionSnapshotSchema = z.object({
  revision_id: z.string(),
  phase: z.string(),
  version: z.number().int().optional(),
  goal: z.string().optional(),
  constraints: ParsedConstraintsSchema.optional(),
  plan: PlanSchema,
}).passthrough();

export const GraphRunEventSchema = z.object({
  run_id: z.string(),
  thread_id: z.string(),
  plan_id: z.string(),
  revision_id: z.string(),
  phase: z.string(),
  revision: PlanRevisionSnapshotSchema,
});
```

Update `PlanResponseSchema`:

```ts
export const PlanResponseSchema = z.object({
  plan_id: z.string().optional(),
  revision: PlanRevisionSnapshotSchema.optional(),
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
}).passthrough();
```

Export inferred types in `types/weekendpilot.ts`:

```ts
export type GraphRunStartResponse = z.infer<typeof GraphRunStartResponseSchema>;
export type GraphRunEvent = z.infer<typeof GraphRunEventSchema>;
export type ResumeDecision =
  | { decision: 'approve'; selected_action_ids: string[] }
  | { decision: 'reject' };
```

- [ ] **Step 4: Run tests**

Run:

```bash
npm run test:contracts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/contracts/schemas.ts types/weekendpilot.ts tests/contracts
git commit -m "test: align frontend contracts with graph run workflow"
```

---

## Task 2: Replace Planner API Client With Graph-Run Contract

**Files:**
- Modify: `features/planner/apiClient.ts`
- Modify: `tests/frontend/planner-api-client.test.tsx`

- [ ] **Step 1: Replace API client test expectations**

Use this endpoint sequence:

```ts
import {
  getHealth,
  getPlan,
  getPlanVersions,
  getToolSchemas,
  getTraces,
  listPlans,
  rejectPlan,
  resumePlan,
  startPlanRun,
} from '../../features/planner/apiClient';

test('planner API client uses graph-run workflow endpoints', async () => {
  delete process.env.NEXT_PUBLIC_API_URL;
  const calls = installFetch({ plan: { id: 'plan_client_001' }, run_id: 'run_1', thread_id: 'thread_1', plan_id: 'plan_client_001' });

  await startPlanRun('家庭半日计划', 'local_demo_user');
  await listPlans();
  await getPlan('plan_client_001');
  await resumePlan('plan_client_001', ['act_msg_001']);
  await rejectPlan('plan_client_001');
  await getPlanVersions('plan_client_001');
  await getTraces('plan_client_001');
  await getToolSchemas();
  await getHealth();

  assert.deepEqual(calls.map((call) => [call.url, call.init?.method ?? 'GET']), [
    ['http://127.0.0.1:8787/api/plans/runs', 'POST'],
    ['http://127.0.0.1:8787/api/plans', 'GET'],
    ['http://127.0.0.1:8787/api/plans/plan_client_001', 'GET'],
    ['http://127.0.0.1:8787/api/plans/plan_client_001/resume', 'POST'],
    ['http://127.0.0.1:8787/api/plans/plan_client_001/resume', 'POST'],
    ['http://127.0.0.1:8787/api/plans/plan_client_001/versions', 'GET'],
    ['http://127.0.0.1:8787/api/traces/plan_client_001', 'GET'],
    ['http://127.0.0.1:8787/api/tool-schemas', 'GET'],
    ['http://127.0.0.1:8787/api/health', 'GET'],
  ]);

  assert.equal(calls[0].init?.body, JSON.stringify({ goal: '家庭半日计划', user_id: 'local_demo_user' }));
  assert.equal(calls[3].init?.body, JSON.stringify({ decision: 'approve', selected_action_ids: ['act_msg_001'] }));
  assert.equal(calls[4].init?.body, JSON.stringify({ decision: 'reject' }));
});
```

- [ ] **Step 2: Run frontend API test and confirm failure**

Run:

```bash
npm run test:frontend -- tests/frontend/planner-api-client.test.tsx
```

Expected: FAIL because old functions and URLs are still present.

- [ ] **Step 3: Implement graph-run API client**

Replace legacy functions with:

```ts
export async function startPlanRun(goal: string, userId = 'local_demo_user') {
  return apiRequest<GraphRunStartResponse>('/api/plans/runs', {
    method: 'POST',
    body: { goal, user_id: userId },
  });
}

export async function getPlan(planId: string) {
  return apiRequest<PlanResponse>(`/api/plans/${planId}`);
}

export async function listPlans() {
  return apiRequest<PlanListResponse>('/api/plans');
}

export async function resumePlan(planId: string, selectedActionIds: string[]) {
  return apiRequest<PlanResponse>(`/api/plans/${planId}/resume`, {
    method: 'POST',
    body: { decision: 'approve', selected_action_ids: selectedActionIds },
  });
}

export async function rejectPlan(planId: string) {
  return apiRequest<PlanResponse>(`/api/plans/${planId}/resume`, {
    method: 'POST',
    body: { decision: 'reject' },
  });
}

export async function getPlanVersions(planId: string) {
  return apiRequest<{ plan_id: string; versions: Array<Record<string, unknown>> }>(`/api/plans/${planId}/versions`);
}
```

Implement SSE helper:

```ts
export function streamRunUpdates(
  runId: string,
  callbacks: {
    onGraphUpdate?: (event: GraphRunEvent) => void | Promise<void>;
    onError?: (error: Error) => void;
  },
) {
  const es = new EventSource(resolveApiUrl(`/api/plans/runs/${runId}/stream`));

  es.addEventListener('graph_update', (event) => {
    void callbacks.onGraphUpdate?.(JSON.parse((event as MessageEvent).data));
  });

  es.onerror = () => {
    if (es.readyState === EventSource.CLOSED) {
      callbacks.onError?.(new Error('SSE connection failed'));
    }
  };

  return () => es.close();
}
```

- [ ] **Step 4: Search for removed API names**

Run:

```bash
rg -n "buildPlan|buildPlanStream|patchConstraints|buildAlternatives|confirmPlan|executePlan|recoverPlan|revisePlan|/api/plans/build|/confirm|/execute|/recover|/constraints|/alternatives|/revise" features components app tests/frontend lib types
```

Expected: only intentional failing references in files not yet migrated.

- [ ] **Step 5: Commit**

```bash
git add features/planner/apiClient.ts tests/frontend/planner-api-client.test.tsx
git commit -m "feat: switch planner client to graph run api"
```

---

## Task 3: Rebuild Plan State Machine Around Runs And Resume

**Files:**
- Modify: `features/planner/usePlanMachine.ts`
- Modify: `types/views.ts`

- [ ] **Step 1: Add graph-run state fields**

Update `PlanState`:

```ts
export type GraphPhase =
  | 'idle'
  | 'planning'
  | 'needs_clarification'
  | 'validation_failed'
  | 'pending_approval'
  | 'executing'
  | 'partially_completed'
  | 'completed'
  | 'cancelled'
  | 'failed';

export type PlanPhase =
  | 'idle'
  | 'planning'
  | 'clarifying'
  | 'results'
  | 'executing'
  | 'completed';

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
```

- [ ] **Step 2: Replace action key logic**

Use backend durable ids first:

```ts
export function getActionKey(action: Record<string, unknown>): string {
  return String(action.action_id ?? action.id ?? `${action.tool ?? action.type}_${action.target ?? action.label ?? action.place_id ?? 'default'}`);
}

function selectableActions(result: PlanResponse | null) {
  const actions = ((result?.actions?.length ? result.actions : result?.plan.actions) ?? []) as Array<Record<string, unknown>>;
  return actions.filter((action) => String(action.status ?? 'pending') === 'pending');
}
```

- [ ] **Step 3: Rewrite `startPlan` flow**

The flow should:

1. Dispatch `START_PLAN`.
2. Call `startPlanRun`.
3. Dispatch run metadata.
4. Subscribe to `streamRunUpdates`.
5. Fetch `getPlan(plan_id)` after the graph update.
6. Dispatch result by backend phase.

Reducer behavior:

```ts
case 'RUN_STARTED':
  return {
    ...state,
    runId: action.run.run_id,
    threadId: action.run.thread_id,
    planId: action.run.plan_id,
    progress: ['Graph run created'],
    currentStep: 1,
  };
case 'GRAPH_UPDATED':
  return {
    ...state,
    graphPhase: action.event.phase as GraphPhase,
    revisionId: action.event.revision_id,
    progress: [...state.progress, `Graph phase: ${action.event.phase}`],
    currentStep: state.currentStep + 1,
  };
case 'PLAN_LOADED': {
  const phase = String(action.result.revision?.phase ?? action.result.plan.status);
  const pending = selectableActions(action.result);
  return {
    ...state,
    phase: phase === 'needs_clarification' ? 'clarifying' : 'results',
    graphPhase: phase as GraphPhase,
    planId: action.result.plan_id ?? action.result.plan.id,
    revisionId: action.result.revision?.revision_id ?? state.revisionId,
    result: action.result,
    selectedActions: new Set(pending.map(getActionKey)),
    receipts: action.result.receipts ?? [],
    error: null,
  };
}
```

- [ ] **Step 4: Rewrite approval flow**

Replace `confirmAndExecute`:

```ts
const approveSelectedActions = useCallback(async () => {
  const planId = state.planId ?? state.result?.plan.id;
  if (!planId) return;
  const selected = Array.from(state.selectedActions);
  if (!selected.length) {
    dispatch({ type: 'EXECUTE_FAILED', error: '请选择至少一项待执行动作' });
    return;
  }

  dispatch({ type: 'START_EXECUTE' });
  try {
    const result = await resumePlan(planId, selected);
    dispatch({ type: 'EXECUTE_LOADED', result });
  } catch (err) {
    dispatch({ type: 'EXECUTE_FAILED', error: err instanceof Error ? err.message : '执行失败' });
  }
}, [state.planId, state.result, state.selectedActions]);
```

Add reject:

```ts
const rejectCurrentPlan = useCallback(async () => {
  const planId = state.planId ?? state.result?.plan.id;
  if (!planId) return;
  dispatch({ type: 'SET_LOADING', action: 'approval', message: '正在取消当前计划...' });
  try {
    const result = await rejectPlan(planId);
    dispatch({ type: 'PLAN_LOADED', result });
  } catch (err) {
    dispatch({ type: 'PLAN_FAILED', error: err instanceof Error ? err.message : '取消失败' });
  }
}, [state.planId, state.result]);
```

- [ ] **Step 5: Remove old frontend actions**

Delete state/actions and returned callbacks for:

- `loadAlternatives`
- `updateConstraints`
- `regenerateWithFeedback`
- `replaceNode`
- `recoverCurrentPlan`
- `goToConfirm`

Keep the plan view read-only until backend exposes graph-native revision/rescue endpoints.

- [ ] **Step 6: Run focused tests**

Run:

```bash
npm run test:frontend
```

Expected: failures only from UI components still expecting old callbacks; fix in later tasks.

- [ ] **Step 7: Commit**

```bash
git add features/planner/usePlanMachine.ts types/views.ts
git commit -m "feat: model planner state as graph run workflow"
```

---

## Task 4: Build Action Ledger Inspector

**Files:**
- Create: `components/plan/ActionLedgerPanel.tsx`
- Create: `tests/frontend/action-ledger-panel.test.tsx`
- Modify: `app/globals.css`

- [ ] **Step 1: Write component test**

```tsx
test('action ledger panel selects durable action ids and disables approval with no selection', () => {
  const toggled: string[] = [];
  let approved = 0;
  let rejected = 0;

  const html = renderToStaticMarkup(
    <ActionLedgerPanel
      actions={[
        { action_id: 'act_msg_001', tool: 'messaging', type: 'send_plan_message', label: '发送计划', detail: '发送给同行人', status: 'pending', payload: {} },
        { action_id: 'act_cal_001', tool: 'calendar', type: 'create_calendar_event', label: '创建日历', detail: '写入日程', status: 'succeeded', payload: {} },
      ]}
      selectedActions={new Set(['act_msg_001'])}
      executing={false}
      onToggleAction={(id) => toggled.push(id)}
      onSelectAll={() => {}}
      onDeselectAll={() => {}}
      onApprove={() => { approved += 1; }}
      onReject={() => { rejected += 1; }}
    />,
  );

  assert.match(html, /act_msg_001/);
  assert.match(html, /发送计划/);
  assert.match(html, /已完成/);
});
```

- [ ] **Step 2: Implement `ActionLedgerPanel`**

Core behavior:

```tsx
export function ActionLedgerPanel({
  actions,
  selectedActions,
  executing,
  onToggleAction,
  onSelectAll,
  onDeselectAll,
  onApprove,
  onReject,
}: ActionLedgerPanelProps) {
  const pending = actions.filter((action) => String(action.status ?? 'pending') === 'pending');
  const selectedCount = selectedActions.size;

  return (
    <aside className="action-ledger-panel" aria-label="执行账本">
      <div className="action-ledger-header">
        <span>Action Ledger</span>
        <strong>{selectedCount} / {pending.length}</strong>
      </div>

      <div className="action-ledger-toolbar">
        <button type="button" onClick={onSelectAll} disabled={!pending.length || executing}>全选待执行</button>
        <button type="button" onClick={onDeselectAll} disabled={!selectedCount || executing}>清空</button>
      </div>

      <div className="action-ledger-list">
        {actions.map((action) => {
          const id = String(action.action_id ?? action.id);
          const status = String(action.status ?? 'pending');
          const disabled = status !== 'pending' || executing;
          return (
            <button
              key={id}
              type="button"
              className={`ledger-action ${selectedActions.has(id) ? 'selected' : ''} ledger-action--${status}`}
              disabled={disabled}
              onClick={() => onToggleAction(id)}
              aria-pressed={selectedActions.has(id)}
            >
              <span className="ledger-action-status">{statusLabel(status)}</span>
              <strong>{action.label ?? action.tool ?? action.type}</strong>
              <small>{action.detail ?? id}</small>
              <code>{id}</code>
            </button>
          );
        })}
      </div>

      <div className="action-ledger-footer">
        <button className="secondary-button" type="button" onClick={onReject} disabled={executing}>取消计划</button>
        <button className="primary-button" type="button" onClick={onApprove} disabled={!selectedCount || executing}>
          {executing ? '执行中...' : '批准执行'}
        </button>
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: Add styling**

Add CSS using current variables:

```css
.action-ledger-panel {
  position: sticky;
  top: 20px;
  align-self: start;
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: color-mix(in srgb, var(--panel) 92%, var(--blue-soft));
  box-shadow: var(--shadow-sm);
}

.action-ledger-header,
.action-ledger-toolbar,
.action-ledger-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.action-ledger-list {
  display: grid;
  gap: 8px;
}

.ledger-action {
  width: 100%;
  display: grid;
  gap: 4px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  color: var(--text);
  text-align: left;
}

.ledger-action.selected {
  border-color: var(--blue);
  background: var(--blue-soft);
}

.ledger-action:disabled {
  cursor: default;
  opacity: 0.72;
}

.ledger-action code {
  color: var(--subtle);
  font-size: 11px;
}
```

- [ ] **Step 4: Run test**

Run:

```bash
npm run test:frontend -- tests/frontend/action-ledger-panel.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add components/plan/ActionLedgerPanel.tsx tests/frontend/action-ledger-panel.test.tsx app/globals.css
git commit -m "feat: add graph action ledger inspector"
```

---

## Task 5: Convert Plan Results Into Mac-Style Workbench

**Files:**
- Create: `components/plan/GraphRunStatusRail.tsx`
- Create: `components/plan/WorkbenchTabs.tsx`
- Modify: `components/plan/PlanResultsView.tsx`
- Modify: `app/page.tsx`
- Modify: `app/globals.css`
- Modify: `tests/frontend/plan-results-open-domain.test.tsx`

- [ ] **Step 1: Define `PlanResultsView` props**

Replace old unsupported callbacks with graph-native ones:

```ts
type PlanResultsViewProps = {
  result: PlanResponse;
  selectedActions: Set<string>;
  executing: boolean;
  onToggleAction: (key: string) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
  onApprove: () => void;
  onReject: () => void;
  error: string | null;
};
```

- [ ] **Step 2: Add status rail**

```tsx
export function GraphRunStatusRail({ result }: { result: PlanResponse }) {
  const phase = String(result.revision?.phase ?? result.plan.status);
  const revisionId = result.revision?.revision_id ?? 'unversioned';
  const actionCount = (result.actions?.length ? result.actions : result.plan.actions ?? []).length;

  return (
    <section className="graph-status-rail" aria-label="Graph run status">
      <div><span>Phase</span><strong>{phase}</strong></div>
      <div><span>Revision</span><strong>{revisionId}</strong></div>
      <div><span>Actions</span><strong>{actionCount}</strong></div>
      <div><span>Validation</span><strong>{phase === 'validation_failed' ? '需处理' : '已通过'}</strong></div>
    </section>
  );
}
```

- [ ] **Step 3: Add workbench tabs**

```tsx
export type WorkbenchTab = 'plan' | 'evidence' | 'trace';

export function WorkbenchTabs({ value, onChange }: { value: WorkbenchTab; onChange: (value: WorkbenchTab) => void }) {
  return (
    <div className="workbench-tabs" role="tablist" aria-label="工作台视图">
      {([
        ['plan', '计划'],
        ['evidence', '证据'],
        ['trace', 'Graph'],
      ] as const).map(([key, label]) => (
        <button
          key={key}
          type="button"
          role="tab"
          aria-selected={value === key}
          className={value === key ? 'active' : ''}
          onClick={() => onChange(key)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Recompose `PlanResultsView`**

Work with existing components but remove unsupported controls:

```tsx
export function PlanResultsView({
  result,
  selectedActions,
  executing,
  onToggleAction,
  onSelectAll,
  onDeselectAll,
  onApprove,
  onReject,
  error,
}: PlanResultsViewProps) {
  const [activeTab, setActiveTab] = useState<WorkbenchTab>('plan');
  const plan = result.plan;
  const actions = (result.actions?.length ? result.actions : plan.actions) ?? [];

  return (
    <section className="graph-workbench">
      {error && <div className="plan-error-banner" role="alert">{error}</div>}
      <div className="graph-workbench-main">
        <header className="plan-results-header">
          <div>
            <span className="plan-results-kicker">WeekendPilot Graph Run</span>
            <h1>{plan.title}</h1>
            {plan.summary && <p>{plan.summary}</p>}
          </div>
          {plan.badges?.length > 0 && (
            <div className="plan-badges" aria-label="方案标签">
              {plan.badges.map((badge) => <span key={badge}>{badge}</span>)}
            </div>
          )}
        </header>

        <GraphRunStatusRail result={result} />
        <WorkbenchTabs value={activeTab} onChange={setActiveTab} />

        {activeTab === 'plan' && (
          <>
            <ConstraintChips constraints={result.constraints} editable={false} />
            <OverviewCard overview={plan.overview ?? {}} constraintFit={plan.constraint_fit} />
            <ItineraryTimeline itinerary={plan.itinerary ?? []} />
            {result.route && <RouteMap route={result.route as any} />}
          </>
        )}

        {activeTab === 'evidence' && (
          <CandidateInsights
            candidateSets={(result as any).candidate_sets}
            validationIssues={(result as any).validation_issues ?? []}
          />
        )}

        {activeTab === 'trace' && (
          <TracePanel trace={result.trace ?? []} toolCalls={result.tool_calls ?? []} />
        )}
      </div>

      <ActionLedgerPanel
        actions={actions as any}
        selectedActions={selectedActions}
        executing={executing}
        onToggleAction={onToggleAction}
        onSelectAll={onSelectAll}
        onDeselectAll={onDeselectAll}
        onApprove={onApprove}
        onReject={onReject}
      />
    </section>
  );
}
```

- [ ] **Step 5: Update `app/page.tsx`**

Remove `confirming` branch. In `results`, pass graph-native props:

```tsx
<PlanResultsView
  result={state.result}
  selectedActions={state.selectedActions}
  executing={state.phase === 'executing'}
  onToggleAction={machine.toggleAction}
  onSelectAll={machine.selectAllActions}
  onDeselectAll={machine.deselectAllActions}
  onApprove={machine.approveSelectedActions}
  onReject={machine.rejectCurrentPlan}
  error={state.error}
/>
```

- [ ] **Step 6: Add workbench CSS**

```css
.graph-workbench {
  width: min(1180px, 100%);
  margin: 0 auto;
  padding: 20px 18px 96px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 18px;
}

.graph-workbench-main {
  min-width: 0;
  display: grid;
  gap: 18px;
}

.graph-status-rail {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--surface);
}

.graph-status-rail div {
  display: grid;
  gap: 3px;
  padding: 8px 10px;
  border-radius: 10px;
  background: var(--panel);
}

.graph-status-rail span {
  color: var(--muted);
  font-size: 11px;
}

.graph-status-rail strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.workbench-tabs {
  width: fit-content;
  display: inline-flex;
  gap: 3px;
  padding: 3px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface-2);
}

.workbench-tabs button {
  min-width: 72px;
  padding: 7px 12px;
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  font-weight: 650;
}

.workbench-tabs button.active {
  background: var(--panel);
  color: var(--text);
  box-shadow: var(--shadow-sm);
}

@media (max-width: 960px) {
  .graph-workbench {
    grid-template-columns: 1fr;
  }

  .action-ledger-panel {
    position: static;
  }

  .graph-status-rail {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
```

- [ ] **Step 7: Run frontend tests**

Run:

```bash
npm run test:frontend
```

Expected: any failures are from saved-plan old API flow, fixed in Task 6.

- [ ] **Step 8: Commit**

```bash
git add components/plan/GraphRunStatusRail.tsx components/plan/WorkbenchTabs.tsx components/plan/PlanResultsView.tsx app/page.tsx app/globals.css tests/frontend/plan-results-open-domain.test.tsx
git commit -m "feat: redesign planner as graph workbench"
```

---

## Task 6: Update Saved Plans To Resume Pending Actions

**Files:**
- Modify: `features/planner/usePlans.ts`
- Modify: `tests/frontend/interactive-components.test.tsx`
- Modify: `types/api.ts`

- [ ] **Step 1: Update plan summary status type**

```ts
export type PlanStatus =
  | 'pending_approval'
  | 'partially_completed'
  | 'completed'
  | 'cancelled'
  | 'validation_failed'
  | 'saved'
  | 'executing';
```

- [ ] **Step 2: Rewrite saved plan execute test**

The saved plan shortcut must load the plan, then resume pending actions:

```ts
test('saved plans view resumes pending backend actions', async () => {
  const calls: Array<{ url: string; method: string; body?: string }> = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? 'GET';
    calls.push({ url, method, body: String(init?.body ?? '') });
    if (url.endsWith('/api/plans') && method === 'GET') {
      return jsonResponse({ plans: [makePlanSummary()], total: 1 });
    }
    if (url.endsWith('/api/plans/plan_001') && method === 'GET') {
      return jsonResponse({
        plan_id: 'plan_001',
        plan: { ...makePlanSummary(), id: 'plan_001', actions: [{ action_id: 'act_msg_001', tool: 'messaging', type: 'send_plan_message', label: '发送计划', status: 'pending', payload: {} }] },
        actions: [{ action_id: 'act_msg_001', tool: 'messaging', type: 'send_plan_message', label: '发送计划', status: 'pending', payload: {} }],
        pending_actions: [],
        receipts: [],
        constraints: makeConstraintsFixture(),
      });
    }
    if (url.endsWith('/api/plans/plan_001/resume')) {
      return jsonResponse({
        plan: { ...makePlanSummary(), id: 'plan_001', status: 'completed', actions: [] },
        actions: [],
        pending_actions: [],
        receipts: [{ id: 'rcpt_1', action_id: 'act_msg_001', tool: 'messaging', type: 'send_plan_message', status: 'succeeded', detail: 'messaging completed', payload: {} }],
        constraints: makeConstraintsFixture(),
      });
    }
    return jsonResponse({});
  }) as typeof fetch;

  const { container } = render(<SavedPlansView />);

  await waitFor(() => byTestId(container, 'plan-execute-plan_001'));
  await click(byTestId(container, 'plan-execute-plan_001'));
  await waitFor(() => {
    assert.ok(calls.some((call) => call.url.endsWith('/api/plans/plan_001') && call.method === 'GET'));
    assert.ok(calls.some((call) => call.url.endsWith('/api/plans/plan_001/resume') && call.method === 'POST'));
    assert.ok(calls.some((call) => call.body.includes('"selected_action_ids":["act_msg_001"]')));
  });
});
```

- [ ] **Step 3: Update `usePlans.execute`**

```ts
const execute = useCallback(async (planId: string) => {
  setPlans((prev) => prev.map((p) => (p.id === planId ? { ...p, status: 'executing' } : p)));
  const loaded = await getPlan(planId);
  const pending = ((loaded.actions?.length ? loaded.actions : loaded.plan.actions) ?? [])
    .filter((action: any) => String(action.status ?? 'pending') === 'pending')
    .map((action: any) => String(action.action_id ?? action.id))
    .filter(Boolean);

  if (!pending.length) {
    const summary = summaryFromPlanResponse(loaded);
    setPlans((prev) => prev.map((p) => (p.id === planId ? summary : p)));
    return summary;
  }

  const result = await resumePlan(planId, pending);
  const summary = summaryFromPlanResponse(result);
  setPlans((prev) => prev.map((p) => (p.id === planId ? summary : p)));
  return summary;
}, []);
```

- [ ] **Step 4: Run test**

Run:

```bash
npm run test:frontend -- tests/frontend/interactive-components.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add features/planner/usePlans.ts types/api.ts tests/frontend/interactive-components.test.tsx
git commit -m "feat: resume saved plans through action ledger"
```

---

## Task 7: Remove Deprecated Frontend Code Paths

**Files:**
- Modify/delete as needed:
  - `components/confirm/ConfirmView.tsx`
  - `components/confirm/ActionToggle.tsx`
  - `components/confirm/ExecuteButton.tsx`
  - `components/plan/VariantSelector.tsx`
  - `components/recovery/RecoveryBanner.tsx`
  - `components/planner/BottomExecutionBar.tsx`
  - `components/planner/ConfirmationDialog.tsx`
  - tests that only cover removed legacy UI

- [ ] **Step 1: Search old symbols**

Run:

```bash
rg -n "ConfirmView|ActionToggle|ExecuteButton|VariantSelector|RecoveryBanner|BottomExecutionBar|ConfirmationDialog|buildAlternatives|patchConstraints|recoverPlan|revisePlan|confirmPlan|executePlan|/api/plans/build|/constraints|/alternatives|/confirm|/execute|/recover|/revise" app components features tests/frontend lib types
```

Expected: every match is either removed in this task or proven still used by graph-native UI.

- [ ] **Step 2: Delete dead files**

Only delete files after imports are gone. Prefer deleting frontend-only legacy components that have no caller.

- [ ] **Step 3: Remove dead CSS blocks**

Search CSS class names before deleting:

```bash
rg -n "confirm-view|action-toggle|execute-button|variant-selector|recovery-banner|bottom-execution|confirmation-dialog" app/globals.css components tests/frontend
```

Remove CSS blocks only when the component is deleted or no longer renders them.

- [ ] **Step 4: Run full frontend tests**

Run:

```bash
npm run test:frontend
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app components features tests/frontend
git commit -m "chore: remove deprecated planner frontend paths"
```

---

## Task 8: End-To-End Verification

**Files:**
- No code unless verification finds failures.

- [ ] **Step 1: Static search gate**

Run:

```bash
rg -n "/api/plans/build|/api/plans/.*/constraints|/api/plans/.*/alternatives|/api/plans/.*/confirm|/api/plans/.*/execute|/api/plans/.*/recover|/api/plans/.*/revise|buildPlan\\(|patchConstraints|buildAlternatives|confirmPlan|executePlan|recoverPlan|revisePlan" app components features lib types tests/frontend
```

Expected: no matches.

- [ ] **Step 2: Run all contract/frontend/backend tests**

Run:

```bash
npm run test:contracts
npm run test:frontend
uv run pytest tests/backend -q
```

Expected:

- Contract tests pass.
- Frontend tests pass.
- Backend tests pass.

- [ ] **Step 3: Build**

Run:

```bash
npm run build
```

Expected: Next.js build succeeds.

- [ ] **Step 4: Manual smoke**

Start services:

```bash
npm run dev:full
```

In browser:

1. Create a plan from the home composer.
2. Verify graph status rail reaches `pending_approval`.
3. Select one pending action in the action ledger.
4. Click approve.
5. Verify receipts render and the plan becomes `partially_completed` or `completed`.
6. Open saved plans and verify pending/partial plans can resume.

- [ ] **Step 5: Final commit**

```bash
git status --short
git add .
git commit -m "feat: redesign frontend around graph run workflow"
```

---

## Self-Review

**Spec coverage:** This plan covers graph-run API migration, Mac-style planner workbench, action-ledger approval, saved plan resume, visual theme preservation, and deprecated frontend path cleanup.

**Placeholder scan:** No task relies on `TBD` or unspecified "handle later" work. Unsupported old frontend interactions are intentionally removed until backend exposes graph-native revision/recovery APIs.

**Type consistency:** Durable action identity is consistently `action_id`; frontend fallback to `id` exists only for resilience. Backend phase is consistently read from `result.revision?.phase ?? result.plan.status`.
