# Full Detailed Design Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the current WeekendPilot project into full alignment with `detailed_design.md`, covering product experience, frontend/backend integration, final Agent architecture, data quality, tools, execution safety, recovery, observability, tests, and docs.

**Architecture:** Replace the current split between frontend mock and Python-only local backend with a single Next.js App Router workbench backed by TypeScript route handlers, a LangGraph durable workflow, OpenAI Responses/Agents SDK tool execution, PostgreSQL/PostGIS/pgvector data access, Redis-compatible cache boundaries, MCP-ready adapters, guardrails, human confirmation gates, and trace-first UI. Keep the existing Python backend as a transitional reference until the TypeScript path has parity tests, then mark it as legacy in docs.

**Tech Stack:** Next.js App Router, React 19, TypeScript, OpenAI JavaScript SDK, `@openai/agents`, LangGraph JavaScript, Zod, PostgreSQL with PostGIS and pgvector, Redis-compatible cache adapter, Mapbox GL JS with route-provider abstraction, OpenTelemetry, Playwright, Node test runner, pytest for legacy regression during migration.

---

## Scope Check

The detailed design spans multiple independent subsystems: UI information architecture, API integration, Agent runtime, durable workflow, data platform, map/routing, execution adapters, safety, observability, demo assets, and documentation. This file is the master alignment plan. Execute tasks in order because later tasks depend on shared contracts, but keep commits per task so work can be reviewed and reverted independently.

## Reference Sources Checked

- Local baseline: `detailed_design.md`, `docs/detailed_design_gap_analysis.md`, current frontend files, current Python backend files, and current tests.
- OpenAI official docs: JavaScript SDK uses `client.responses.create(...)`; Agents SDK is documented as supporting tools, handoffs, guardrails, human-in-the-loop, sessions, and tracing.
- LangGraph official docs: durable execution requires a checkpointer, a thread identifier, deterministic/idempotent replay boundaries, and side effects wrapped in tasks.

## File Structure

Create these focused TypeScript modules:

- `types/weekendpilot.ts`: canonical API/domain types shared by frontend, route handlers, Agent graph, and tests.
- `lib/contracts/schemas.ts`: Zod schemas for user goals, constraints, POI, itinerary, actions, receipts, recovery diffs, trace spans, and API payloads.
- `lib/data/db.ts`: PostgreSQL connection boundary.
- `lib/data/migrations/*.sql`: database schema for POI, coupons, menus, route legs, availability, user profiles, plans, checkpoints, traces, executions, and idempotency keys.
- `lib/data/seed/*.json`: curated seed data source files split by POI, coupons, menus, routes, failure scenarios, and demo profiles.
- `lib/data/repositories/*.ts`: typed data access for POI, coupons, menus, routes, availability, traces, plans, checkpoints, idempotency, and user profile.
- `lib/cache/cache.ts`: Redis-compatible cache interface with local in-memory fallback for tests.
- `lib/tools/*.ts`: MCP-ready tool adapters for all 15 tools in the detailed design.
- `lib/agent/state.ts`: LangGraph state schema and state helpers.
- `lib/agent/nodes/*.ts`: deterministic graph nodes for parse, context, search, ranking, route, validation, confirmation, execution, recovery, and summary.
- `lib/agent/graph.ts`: LangGraph graph construction, checkpointer configuration, pause/resume, and stream helpers.
- `lib/agent/openai.ts`: OpenAI Responses and Agents SDK configuration.
- `lib/agent/guardrails.ts`: no hallucinated POI, confirmation, privacy, and side-effect guardrails.
- `lib/observability/tracing.ts`: OpenTelemetry and Agent trace normalization.
- `app/api/plans/*/route.ts`: Next.js route handlers for build, fetch, patch constraints, alternatives, confirm, execute, recover, traces, health, and tool schemas.
- `features/planner/apiClient.ts`: frontend API client replacing direct mock calls.
- `features/planner/plannerReducer.ts`: frontend state reducer for streaming, confirmation, execution, and recovery.
- `components/planner/*.tsx`: focused Planner UI components.
- `components/map/RouteMap.tsx`: Mapbox GL route view with deterministic fallback for test/demo.
- `components/trace/TracePanel.tsx`: expandable trace and tool-call inspector.
- `tests/contracts/*.test.ts`: schema and contract tests.
- `tests/server/*.test.ts`: route handler, Agent graph, repository, tool, guardrail, and recovery tests.
- `tests/frontend/*.test.tsx`: reducer and component tests.
- `tests/e2e/*.spec.ts`: browser smoke tests for desktop and mobile flows.

Modify these existing files:

- `package.json`: add TypeScript, testing, database, map, OpenAI, LangGraph, observability, and Playwright scripts/dependencies.
- `next.config.mjs`: enable server external package handling needed by database/OpenTelemetry packages.
- `jsconfig.json`: replace with `tsconfig.json` while preserving `@/*` path alias.
- `app/page.jsx`: migrate to `app/page.tsx`.
- `app/layout.jsx`: migrate to `app/layout.tsx`.
- `app/globals.css`: update layout for one-screen workbench, bottom confirmation bar, mobile three-stage layout, and trace/map panels.
- `components/*.jsx`: migrate or replace with focused `.tsx` components.
- `features/planner/mockAgent.js`: remove from main path after API integration tests pass; keep deterministic fixtures under `tests/fixtures`.
- `src/agent.mjs`: remove from main path after frontend tests no longer import it; keep as legacy fixture only if needed by old submission tests.
- `README.md`, `backend/README.md`, `design_submission.md`: update claims to match final implementation.
- `docs/detailed_design_gap_analysis.md`: replace with final closure report after all tasks pass.

## Coverage Matrix

| detailed_design section | Requirement | Implemented by |
|---|---|---|
| 1/1.1 | Execution-type local-life Agent, scoring alignment, business loop | Tasks 2, 4, 8, 9, 13, 15, 17 |
| 2 | Responses API, Agents SDK, MCP-ready tools, durable workflow, map summaries, browser fallback | Tasks 4, 5, 6, 8, 10, 11, 13 |
| 3 | No long travel, no hallucinated POI, no unconfirmed payment | Tasks 3, 7, 14, 16 |
| 4 | Family, friends, date, rainy indoor, transaction failure | Tasks 2, 8, 12, 15 |
| 5 | 10-second plan, full itinerary, 100% core constraint scripts, receipts/recovery | Tasks 4, 8, 12, 17 |
| 6 | One-screen workbench, trace, constraints, plan canvas, map, bottom execution, mobile layout | Tasks 3, 9, 17 |
| 7 | Parse/search/rank/route/validate/confirm/execute/recover; clarification state | Tasks 4, 6, 8, 12 |
| 8 | Text/voice/examples, editable constraints, expandable trace, reasons, risks, confirmations, receipts | Tasks 9, 10, 13, 14 |
| 9 | Central orchestrator, state machine, durable workflow, trace store | Tasks 4, 5, 6 |
| 10 | Final tech stack | Tasks 1, 4, 5, 6, 7, 8, 10, 11 |
| 11 | Canonical data structures | Tasks 2, 7 |
| 12 | Filtering, weighted ranking, grounded explanations | Task 8 |
| 13 | 15 tools and business adapters | Tasks 10, 13 |
| 14 | Recovery for restaurant, activity, rain, route, budget, conflict, tool timeout | Task 12 |
| 15 | Privacy, safety, trust, guardrails | Task 14 |
| 16 | Three-act demo, receipts, failure recovery, review views | Tasks 15, 17 |
| 17 | User, Agent, and data capabilities | Tasks 2 through 15 |
| 18 | Milestones | All tasks |
| 19 | Desktop first, mobile responsive, fixed local area, map, payment limits | Tasks 3, 7, 9, 14 |
| 20 | Reference capabilities are represented in implementation | Tasks 4, 5, 6, 10, 11 |

## Execution Rules

- Work in a branch named `codex/full-detailed-design-alignment`.
- Do not delete the Python backend until Task 18 confirms the TypeScript path passes all parity and E2E checks.
- Keep commits per task.
- Every task starts with tests or schema checks, then implementation, then verification.
- Preserve existing user changes. If a file is dirty before a task, inspect it and integrate with it.

---

### Task 1: Baseline Verification And Test Fix

**Files:**
- Modify: `tests/backend/test_llm_client.py`
- Verify: `package.json`
- Verify: `pyproject.toml`

- [ ] **Step 1: Write the failing cross-platform assertion**

Replace the OS-specific assertion in `tests/backend/test_llm_client.py` with a platform-neutral check:

```python
self.assertIn(command[0], {"curl", "curl.exe"})
```

- [ ] **Step 2: Run the focused failing test**

Run: `uv run pytest tests/backend/test_llm_client.py -q`

Expected: PASS with `1 passed`.

- [ ] **Step 3: Run full baseline verification**

Run: `npm test`

Expected: PASS with 6 frontend mock tests.

Run: `uv run pytest tests/backend`

Expected: PASS with 21 backend tests.

Run: `npm run build`

Expected: Next.js production build succeeds.

- [ ] **Step 4: Commit**

```bash
git add tests/backend/test_llm_client.py
git commit -m "test: make llm curl fallback test cross platform"
```

### Task 2: Canonical Contracts And TypeScript Setup

**Files:**
- Create: `tsconfig.json`
- Modify: `package.json`
- Modify: `next.config.mjs`
- Create: `types/weekendpilot.ts`
- Create: `lib/contracts/schemas.ts`
- Create: `tests/contracts/weekendpilot-contracts.test.ts`

- [ ] **Step 1: Add contract tests**

Create `tests/contracts/weekendpilot-contracts.test.ts` with tests that validate:

```typescript
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  ParsedConstraintsSchema,
  PoiSchema,
  PlanResponseSchema,
  ReceiptSchema,
  RecoveryDiffSchema,
} from '../../lib/contracts/schemas';

test('ParsedConstraints accepts the detailed design family example', () => {
  const parsed = ParsedConstraintsSchema.parse({
    scenario: 'family',
    origin: { type: 'current_location', label: 'home', lat: 38.2601, lng: 140.8824 },
    time_window: { date: '2026-05-09', start: '14:00', duration_hours: 4.5, flexible: true },
    people: { adults: 2, children: [{ age: 5 }], relationship: 'family' },
    preferences: {
      distance: 'nearby',
      diet: ['low_fat', 'low_sugar'],
      activity: ['child_friendly', 'not_too_tiring'],
      budget_level: 'medium',
    },
    constraints: { radius_km: 5, max_wait_minutes: 15, avoid: ['heavy_oil', 'long_queue', 'smoking'] },
    required_actions: ['activity_reservation', 'restaurant_reservation', 'send_plan_message'],
  });

  assert.equal(parsed.people.children[0].age, 5);
});

test('POI requires source, place id, availability, rating, review count, and risk fields', () => {
  const poi = PoiSchema.parse({
    id: 'r_014',
    name: 'Green Table',
    category: 'restaurant',
    lat: 38.2618,
    lng: 140.8791,
    distance_km: 2.4,
    open_hours: [{ day: 'sat', start: '11:00', end: '21:00' }],
    rating: 4.6,
    review_count: 1260,
    avg_price: 1800,
    tags: ['healthy', 'child_seat', 'low_fat', 'quiet'],
    wait_minutes: 8,
    booking_supported: true,
    availability: [{ time: '18:10', available: true, capacity: 4 }],
    supported_scenarios: ['family'],
    source: 'seed_verified',
    reason: '低脂套餐和儿童座椅都可用。',
    risk_tags: ['weekend_queue'],
    audience: ['family'],
    district: 'Aoba',
    menu_summary: '低脂套餐、儿童餐、低糖饮品',
    review_summary: '家庭用户评价稳定，等待时间较短。',
  });

  assert.equal(poi.source, 'seed_verified');
});

test('PlanResponse contains variants, tool calls, constraint fit, actions, and receipts surface', () => {
  const response = PlanResponseSchema.parse({
    constraints: {
      scenario: 'family',
      origin: { type: 'current_location', label: 'home', lat: 38.2601, lng: 140.8824 },
      time_window: { date: '2026-05-09', start: '14:00', duration_hours: 4.5, flexible: true },
      people: { adults: 2, children: [{ age: 5 }], relationship: 'family' },
      preferences: { distance: 'nearby', diet: ['low_fat'], activity: ['child_friendly'], budget_level: 'medium' },
      constraints: { radius_km: 5, max_wait_minutes: 15, avoid: ['long_queue'] },
      required_actions: ['activity_reservation'],
    },
    progress: [],
    trace: [],
    tool_calls: [],
    pending_actions: [],
    plan: {
      id: 'plan_contract_001',
      status: 'pending_confirmation',
      title: '亲子科学馆 + 健康轻食半日计划',
      summary: '亲子活动、健康轻食、饭后散步和确认后执行回执。',
      constraint_fit: { distance: 0.95, child_friendly: 1, diet: 0.9, time: 0.92, budget: 0.86 },
      itinerary: [],
      overview: { theme: '下午 · 家庭 · 健康轻松', totalDuration: '4.5 小时', driveTime: '约 25 分钟', walkingDistance: '1.2 公里', estimatedCost: '约 7200 元', score: 91 },
      actions: [],
      variants: [],
    },
  });

  assert.equal(response.plan.constraint_fit.distance, 0.95);
});

test('Receipt and RecoveryDiff match execution and recovery contract', () => {
  const receipt = ReceiptSchema.parse({
    type: 'restaurant_reservation',
    tool: 'create_reservation',
    id: 'RES-20260509-3812',
    status: 'confirmed',
    detail: '已预订 Green Table 18:10 的 3 人桌。',
    payload: { place_id: 'r_014', party_size: 3 },
  });
  const diff = RecoveryDiffSchema.parse({
    changed: 'restaurant',
    reason: 'restaurant_unavailable',
    from: 'Green Table',
    to: 'Light Bowl',
    costDelta: '+约 40 元',
    travelDelta: '+步行 2 分钟',
    preserved: ['亲子科学馆', '河畔低糖甜品散步'],
  });

  assert.match(receipt.id, /^RES-/);
  assert.deepEqual(diff.preserved, ['亲子科学馆', '河畔低糖甜品散步']);
});
```

- [ ] **Step 2: Run contract tests to verify failure**

Run: `node --test tests/contracts/weekendpilot-contracts.test.ts`

Expected: FAIL because TypeScript execution and contract files are not configured.

- [ ] **Step 3: Add TypeScript and schema dependencies**

Run: `npm install zod tsx typescript @types/node`

Expected: `package.json` and `package-lock.json` include the new dependencies.

- [ ] **Step 4: Add scripts**

Modify `package.json` scripts:

```json
{
  "test": "node --test tests/*.test.mjs",
  "test:contracts": "tsx --test tests/contracts/*.test.ts",
  "test:server": "tsx --test tests/server/*.test.ts",
  "test:frontend": "tsx --test tests/frontend/*.test.tsx",
  "test:all": "npm test && npm run test:contracts && npm run test:server && npm run test:frontend"
}
```

- [ ] **Step 5: Create TypeScript config**

Create `tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "es2022"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "paths": {
      "@/*": ["./*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 6: Implement types and schemas**

Create `types/weekendpilot.ts` and `lib/contracts/schemas.ts` with exact schemas used by the test. Include all detailed-design fields: `scenario`, `origin`, `time_window`, `people`, `preferences`, `constraints`, `required_actions`, `constraint_fit`, `tool_calls`, `receipts`, `diff`, and `adjustment`.

- [ ] **Step 7: Run contract tests**

Run: `npm run test:contracts`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add package.json package-lock.json tsconfig.json types/weekendpilot.ts lib/contracts/schemas.ts tests/contracts/weekendpilot-contracts.test.ts
git commit -m "feat: add canonical WeekendPilot contracts"
```

### Task 3: Product Scope Cleanup And One-Workbench Shell

**Files:**
- Rename: `app/page.jsx` to `app/page.tsx`
- Rename: `app/layout.jsx` to `app/layout.tsx`
- Modify: `components/AppChrome.jsx`
- Modify: `components/HomeView.jsx`
- Modify: `components/SavedPlansView.jsx`
- Modify: `components/ActivityView.jsx`
- Modify: `components/SettingsView.jsx`
- Modify: `app/globals.css`
- Create: `tests/frontend/product-scope.test.tsx`

- [ ] **Step 1: Write scope tests**

Create tests that assert:

```typescript
import test from 'node:test';
import assert from 'node:assert/strict';
import { scenarioPrompts } from '../../features/planner/mockAgent';

test('scenario prompts expose all four detailed design entry points', () => {
  assert.deepEqual(Object.keys(scenarioPrompts).sort(), ['date', 'family', 'friends', 'rainy'].sort());
});

test('saved plan examples stay local-life and half-day scoped', () => {
  const forbidden = ['海边短途', '山间休整', '10 月 14 - 15 日', '11 月 03 - 05 日', '山脉景区'];
  const serialized = JSON.stringify(await import('../../features/planner/mockAgent'));
  for (const word of forbidden) {
    assert.equal(serialized.includes(word), false, `forbidden travel copy remains: ${word}`);
  }
});
```

- [ ] **Step 2: Run scope tests to verify failure**

Run: `npm run test:frontend`

Expected: FAIL because the `date` prompt is missing and travel examples remain.

- [ ] **Step 3: Add date scenario and replace travel examples**

Update `features/planner/mockAgent.js` during transition:

```javascript
export const scenarioPrompts = {
  family: '今天下午是空的，想和老婆孩子出去玩几个小时，别离家太远。孩子 5 岁，老婆最近在减脂，帮我安排一下。',
  friends: '今天下午朋友 4 个人出去玩，2 男 2 女，先活动再吃饭，想拍照聊天，预算适中，路线顺一点。',
  date: '下午想和对象约会，安静一点，有氛围，排队少，饭前饭后都顺，别安排太累。',
  rainy: '今天下午可能下雨，帮我找室内活动、舒服的餐厅和轻松路线。'
};
```

Replace saved plans with local half-day examples:

```javascript
export const savedPlans = [
  {
    id: 'family_science_half_day',
    title: '亲子科学馆半日',
    date: '今天 14:00 - 18:30',
    location: '市中心 5 公里内',
    status: '待执行',
    tags: ['家庭', '减脂友好', '半日'],
    accent: 'blue',
    imageClass: 'map'
  },
  {
    id: 'friends_photo_dinner',
    title: '朋友拍照聚餐',
    date: '周六 15:00 - 20:00',
    location: '艺术街区',
    status: '草稿',
    tags: ['朋友', '拍照', '预算适中'],
    accent: 'violet',
    imageClass: 'street'
  },
  {
    id: 'rainy_indoor_backup',
    title: '雨天室内备选',
    date: '周日 13:30 - 18:00',
    location: '商场室内动线',
    status: '已保存',
    tags: ['雨天', '室内', '低等待'],
    accent: 'slate',
    imageClass: 'map'
  }
];
```

- [ ] **Step 4: Convert app entry files to TypeScript**

Rename `app/page.jsx` to `app/page.tsx` and `app/layout.jsx` to `app/layout.tsx`. Preserve current rendering while typing props and event handlers.

- [ ] **Step 5: Reshape shell toward one workbench**

Update `AppChrome` so the primary navigation is collapsed behind one workbench layout. Keep Saved/Activity/Settings as secondary tabs inside the workbench instead of first-class product pages.

- [ ] **Step 6: Run frontend and build tests**

Run: `npm run test:frontend`

Expected: PASS.

Run: `npm run build`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/page.tsx app/layout.tsx components/AppChrome.jsx components/HomeView.jsx components/SavedPlansView.jsx components/ActivityView.jsx components/SettingsView.jsx app/globals.css features/planner/mockAgent.js tests/frontend/product-scope.test.tsx
git rm app/page.jsx app/layout.jsx
git commit -m "feat: align product shell to local half-day scope"
```

### Task 4: Next.js API Routes And Frontend Backend Integration

**Files:**
- Create: `app/api/health/route.ts`
- Create: `app/api/tool-schemas/route.ts`
- Create: `app/api/plans/build/route.ts`
- Create: `app/api/plans/[planId]/route.ts`
- Create: `app/api/plans/[planId]/constraints/route.ts`
- Create: `app/api/plans/[planId]/alternatives/route.ts`
- Create: `app/api/plans/[planId]/confirm/route.ts`
- Create: `app/api/plans/[planId]/execute/route.ts`
- Create: `app/api/plans/[planId]/recover/route.ts`
- Create: `app/api/traces/[planId]/route.ts`
- Create: `features/planner/apiClient.ts`
- Create: `features/planner/plannerReducer.ts`
- Modify: `app/page.tsx`
- Modify: `components/PlannerView.jsx`
- Create: `tests/server/api-routes.test.ts`
- Create: `tests/frontend/planner-api-client.test.ts`

- [ ] **Step 1: Write API route tests**

Create route tests that assert these flows:

```typescript
test('build, fetch, confirm, execute, recover, and traces routes return stable JSON', async () => {
  const build = await postJson('/api/plans/build', {
    goal: '今天下午朋友4个人出去玩，2男2女，先活动再吃饭，想拍照聊天，预算适中',
  });
  assert.equal(build.plan.status, 'pending_confirmation');
  assert.equal(build.plan.actions.length, 6);
  assert.ok(build.tool_calls.length >= 6);

  const planId = build.plan.id;
  const fetched = await getJson(`/api/plans/${planId}`);
  assert.equal(fetched.plan.id, planId);

  const confirmed = await postJson(`/api/plans/${planId}/confirm`, { confirmed: true });
  assert.equal(confirmed.plan.status, 'confirmed');

  const executed = await postJson(`/api/plans/${planId}/execute`, { confirmed: true });
  assert.deepEqual(executed.receipts.map((receipt: { type: string }) => receipt.type), [
    'activity_reservation',
    'restaurant_reservation',
    'coupon',
    'order',
    'message',
    'calendar',
  ]);

  const recovered = await postJson(`/api/plans/${planId}/recover`, { reason: 'restaurant_unavailable' });
  assert.equal(recovered.diff.changed, 'restaurant');

  const traces = await getJson(`/api/traces/${planId}`);
  assert.ok(traces.trace.length >= 1);
});
```

- [ ] **Step 2: Run API tests to verify failure**

Run: `npm run test:server`

Expected: FAIL because route handlers and service registry do not exist.

- [ ] **Step 3: Create TypeScript plan service facade**

Create a temporary TypeScript service under `lib/server/planningService.ts` that mirrors the current Python backend contract using canonical schemas. It must return the same fields that Task 2 validates, including all 6 actions and receipts.

- [ ] **Step 4: Implement route handlers**

Each route imports the TypeScript service and returns `NextResponse.json(...)`. Error mapping must be:

```typescript
const statusByCode: Record<string, number> = {
  validation_error: 400,
  confirmation_required: 403,
  plan_not_found: 404,
  tool_failed: 500,
};
```

- [ ] **Step 5: Implement frontend client**

Create `features/planner/apiClient.ts` with:

```typescript
export async function buildPlan(goal: string) { return request('/api/plans/build', { method: 'POST', body: { goal } }); }
export async function getPlan(planId: string) { return request(`/api/plans/${planId}`); }
export async function patchConstraints(planId: string, body: Record<string, unknown>) { return request(`/api/plans/${planId}/constraints`, { method: 'PATCH', body }); }
export async function buildAlternatives(planId: string) { return request(`/api/plans/${planId}/alternatives`, { method: 'POST', body: {} }); }
export async function confirmPlan(planId: string) { return request(`/api/plans/${planId}/confirm`, { method: 'POST', body: { confirmed: true } }); }
export async function executePlan(planId: string) { return request(`/api/plans/${planId}/execute`, { method: 'POST', body: { confirmed: true } }); }
export async function recoverPlan(planId: string, reason: string) { return request(`/api/plans/${planId}/recover`, { method: 'POST', body: { reason } }); }
```

- [ ] **Step 6: Replace mock main path**

Update `app/page.tsx` so user actions call `features/planner/apiClient.ts`. Move `src/agent.mjs` usage out of the product path.

- [ ] **Step 7: Run tests**

Run: `npm run test:server`

Expected: PASS.

Run: `npm run test:frontend`

Expected: PASS.

Run: `npm run build`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add app/api features/planner/apiClient.ts features/planner/plannerReducer.ts app/page.tsx components/PlannerView.jsx tests/server/api-routes.test.ts tests/frontend/planner-api-client.test.ts lib/server/planningService.ts
git commit -m "feat: connect frontend to Next plan APIs"
```

### Task 5: LangGraph Durable Workflow

**Files:**
- Modify: `package.json`
- Create: `lib/agent/state.ts`
- Create: `lib/agent/graph.ts`
- Create: `lib/agent/nodes/parseConstraints.ts`
- Create: `lib/agent/nodes/buildContext.ts`
- Create: `lib/agent/nodes/searchCandidates.ts`
- Create: `lib/agent/nodes/rankCandidates.ts`
- Create: `lib/agent/nodes/buildItinerary.ts`
- Create: `lib/agent/nodes/validatePlan.ts`
- Create: `lib/agent/nodes/waitForConfirmation.ts`
- Create: `lib/agent/nodes/executeActions.ts`
- Create: `lib/agent/nodes/recoverPlan.ts`
- Create: `tests/server/langgraph-workflow.test.ts`

- [ ] **Step 1: Write workflow tests**

Create tests for deterministic state transitions:

```typescript
test('graph pauses at USER_CONFIRMATION and resumes with the same thread id', async () => {
  const graph = createPlannerGraph({ checkpointer: createTestCheckpointer() });
  const threadId = 'thread_family_001';
  const first = await graph.invoke(
    { goal: '今天下午想和老婆孩子出去玩，孩子5岁，老婆减脂，别太远' },
    { configurable: { thread_id: threadId }, durability: 'sync' },
  );

  assert.equal(first.status, 'USER_CONFIRMATION');
  assert.equal(first.pending_actions.length, 6);

  const resumed = await graph.invoke(
    { confirmed: true },
    { configurable: { thread_id: threadId }, durability: 'sync' },
  );

  assert.equal(resumed.status, 'DONE');
  assert.equal(resumed.receipts.length, 6);
});

test('graph records NEED_CLARIFICATION when goal lacks time and people', async () => {
  const graph = createPlannerGraph({ checkpointer: createTestCheckpointer() });
  const state = await graph.invoke(
    { goal: '帮我安排一下附近活动' },
    { configurable: { thread_id: 'thread_clarify_001' }, durability: 'sync' },
  );

  assert.equal(state.status, 'NEED_CLARIFICATION');
  assert.deepEqual(state.clarifying_questions, ['几个人出行？', '希望从几点开始、玩多久？']);
});
```

- [ ] **Step 2: Run workflow tests to verify failure**

Run: `npm run test:server -- tests/server/langgraph-workflow.test.ts`

Expected: FAIL because LangGraph modules do not exist.

- [ ] **Step 3: Install LangGraph**

Run: `npm install @langchain/langgraph uuid`

Expected: dependencies are added.

- [ ] **Step 4: Implement graph state**

`lib/agent/state.ts` must include statuses:

```typescript
export const PlanStatuses = [
  'INPUT',
  'PARSE_CONSTRAINTS',
  'NEED_CLARIFICATION',
  'SEARCH_CANDIDATES',
  'RANK_AND_FILTER',
  'BUILD_ITINERARY',
  'VALIDATE_PLAN',
  'USER_CONFIRMATION',
  'EXECUTE_ACTIONS',
  'EXECUTION_FAILED',
  'RECOVERY',
  'SEND_SUMMARY',
  'DONE',
] as const;
```

- [ ] **Step 5: Implement graph nodes**

Each node returns a partial state update and appends trace records. `waitForConfirmation` must stop before side effects when `confirmed !== true`. `executeActions` must run only after confirmation.

- [ ] **Step 6: Wire route handlers to graph**

Replace the temporary service in Task 4 with `createPlannerGraph`. Preserve API response shape from Task 2.

- [ ] **Step 7: Run workflow and API tests**

Run: `npm run test:server`

Expected: PASS.

Run: `npm run build`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add package.json package-lock.json lib/agent app/api tests/server/langgraph-workflow.test.ts
git commit -m "feat: add durable LangGraph planner workflow"
```

### Task 6: OpenAI Responses API And Agents SDK Integration

**Files:**
- Modify: `package.json`
- Create: `lib/agent/openai.ts`
- Create: `lib/agent/agents.ts`
- Modify: `lib/agent/nodes/parseConstraints.ts`
- Modify: `lib/agent/nodes/rankCandidates.ts`
- Create: `tests/server/openai-agent-integration.test.ts`

- [ ] **Step 1: Write integration tests with a fake OpenAI client**

The tests must assert structured output parsing, grounded explanation, and fallback:

```typescript
test('parseConstraints uses Responses structured JSON when configured', async () => {
  const fake = {
    responses: {
      create: async () => ({
        output_text: JSON.stringify({
          scenario: 'date',
          origin: { type: 'current_location', label: 'home', lat: 38.2601, lng: 140.8824 },
          time_window: { date: '2026-05-09', start: '15:00', duration_hours: 4.5, flexible: true },
          people: { adults: 2, children: [], relationship: 'date' },
          preferences: { distance: 'nearby', diet: [], activity: ['quiet', 'romantic'], budget_level: 'medium' },
          constraints: { radius_km: 5, max_wait_minutes: 15, avoid: ['long_queue'] },
          required_actions: ['restaurant_reservation', 'send_plan_message'],
        }),
      }),
    },
  };

  const result = await parseConstraintsNode({ goal: '下午想和对象约会，安静一点' }, { openai: fake });
  assert.equal(result.constraints.scenario, 'date');
  assert.equal(result.trace.at(-1).output_summary.llm_fallback, false);
});

test('rank explanation is grounded in score factors and never invents POI facts', async () => {
  const explanation = await explainRankedPoi({
    name: '绿荫轻食餐厅',
    factors: {
      distance_score: 0.95,
      rating_score: 0.92,
      constraint_fit_score: 0.9,
      availability_score: 1,
      route_efficiency_score: 0.88,
      budget_score: 0.86,
      novelty_or_vibe_score: 0.72,
    },
    facts: ['儿童座椅可用', '18:10 可订', '距离上一站步行 8 分钟'],
  });

  assert.deepEqual(explanation.top_reasons, ['儿童座椅可用', '18:10 可订', '距离上一站步行 8 分钟']);
  assert.equal(explanation.top_reasons.some((reason) => reason.includes('停车免费')), false);
});
```

- [ ] **Step 2: Run tests to verify failure**

Run: `npm run test:server -- tests/server/openai-agent-integration.test.ts`

Expected: FAIL because OpenAI integration modules do not exist.

- [ ] **Step 3: Install OpenAI SDK and Agents SDK**

Run: `npm install openai @openai/agents zod@3`

Expected: dependencies are added. Keep existing `zod` compatible with the Agents SDK import path.

- [ ] **Step 4: Implement OpenAI configuration**

`lib/agent/openai.ts` must read:

```typescript
OPENAI_API_KEY
OPENAI_MODEL
OPENAI_BASE_URL
OPENAI_RESPONSES_ENABLED
```

Use deterministic fallback when `OPENAI_RESPONSES_ENABLED !== 'true'`.

- [ ] **Step 5: Implement specialized agents**

`lib/agent/agents.ts` must export:

```typescript
export const intentParserAgentName = 'Intent Parser';
export const rankExplanationAgentName = 'Rank Explanation';
export const recoveryExplanationAgentName = 'Recovery Explanation';
```

Use Agents SDK for instructions, tool metadata, guardrail hooks, and trace metadata. Do not let the Agents SDK execute side-effect tools without graph confirmation state.

- [ ] **Step 6: Wire parse and explanation nodes**

Update parse and ranking nodes so LLM is used only for structured constraints and explanation text. Deterministic rules still decide filtering, scoring, availability, route, confirmation, and execution.

- [ ] **Step 7: Run tests**

Run: `npm run test:server`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add package.json package-lock.json lib/agent/openai.ts lib/agent/agents.ts lib/agent/nodes/parseConstraints.ts lib/agent/nodes/rankCandidates.ts tests/server/openai-agent-integration.test.ts
git commit -m "feat: integrate OpenAI Responses and Agents SDK boundaries"
```

### Task 7: PostgreSQL/PostGIS/pgvector Data Platform

**Files:**
- Modify: `package.json`
- Create: `lib/data/db.ts`
- Create: `lib/data/migrations/001_core_schema.sql`
- Create: `lib/data/migrations/002_indexes.sql`
- Create: `lib/data/seed/pois.json`
- Create: `lib/data/seed/coupons.json`
- Create: `lib/data/seed/menus.json`
- Create: `lib/data/seed/routes.json`
- Create: `lib/data/seed/failureScenarios.json`
- Create: `lib/data/repositories/poiRepository.ts`
- Create: `lib/data/repositories/couponRepository.ts`
- Create: `lib/data/repositories/menuRepository.ts`
- Create: `lib/data/repositories/routeRepository.ts`
- Create: `lib/data/repositories/availabilityRepository.ts`
- Create: `scripts/seed-database.ts`
- Create: `tests/server/data-platform.test.ts`

- [ ] **Step 1: Write data platform tests**

Tests must assert:

```typescript
test('seed catalog has 80 to 120 high-quality local POIs and required coverage', async () => {
  const pois = await loadSeedPois();
  assert.ok(pois.length >= 80 && pois.length <= 120);
  assert.ok(pois.filter((poi) => poi.category === 'restaurant').length >= 24);
  assert.ok(pois.some((poi) => poi.supported_scenarios.includes('family')));
  assert.ok(pois.some((poi) => poi.supported_scenarios.includes('friends')));
  assert.ok(pois.some((poi) => poi.supported_scenarios.includes('date')));
  assert.ok(pois.some((poi) => poi.supported_scenarios.includes('rainy_indoor')));
  for (const poi of pois) {
    assert.ok(poi.id);
    assert.ok(poi.source);
    assert.ok(poi.review_summary.length >= 12);
    assert.ok(poi.menu_summary.length >= 8);
    assert.ok(poi.audience.length >= 1);
    assert.ok(poi.district.length >= 1);
  }
});

test('coupon and menu seeds meet commercial loop requirements', async () => {
  const coupons = await loadSeedCoupons();
  const menus = await loadSeedMenus();
  assert.ok(coupons.length >= 20);
  assert.ok(menus.some((item) => item.tags.includes('low_fat')));
  assert.ok(menus.some((item) => item.tags.includes('low_sugar')));
  assert.ok(coupons.every((coupon) => coupon.rules.includes('退款') || coupon.rules.includes('核销')));
});
```

- [ ] **Step 2: Run tests to verify failure**

Run: `npm run test:server -- tests/server/data-platform.test.ts`

Expected: FAIL because TypeScript seed loaders and repository modules do not exist.

- [ ] **Step 3: Install database packages**

Run: `npm install pg postgres dotenv`

Expected: dependencies are added. Keep repository code behind interfaces so tests can use JSON seeds without a running database.

- [ ] **Step 4: Write migrations**

`001_core_schema.sql` must create:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS pois (
  id text PRIMARY KEY,
  name text NOT NULL,
  category text NOT NULL,
  location geography(Point, 4326) NOT NULL,
  distance_km numeric NOT NULL,
  open_hours jsonb NOT NULL,
  rating numeric NOT NULL,
  review_count integer NOT NULL,
  avg_price integer NOT NULL,
  tags text[] NOT NULL,
  wait_minutes integer NOT NULL,
  booking_supported boolean NOT NULL,
  availability jsonb NOT NULL,
  source text NOT NULL,
  reason text NOT NULL,
  risk_tags text[] NOT NULL,
  supported_scenarios text[] NOT NULL,
  audience text[] NOT NULL,
  district text NOT NULL,
  menu_summary text NOT NULL,
  review_summary text NOT NULL,
  embedding vector(1536)
);
```

Also create `coupons`, `menus`, `route_legs`, `failure_scenarios`, `plans`, `checkpoints`, `traces`, `executions`, and `idempotency_keys`.

- [ ] **Step 5: Curate seeds**

Replace generated repeated names with 80-120 distinct local-life POIs. Keep coverage:

```text
family_activity >= 16
social_activity >= 16
date_activity >= 12
indoor_activity >= 12
restaurant >= 24
dessert_walk/citywalk >= 12
coupons >= 20
failure scenarios >= 5
```

- [ ] **Step 6: Implement repositories**

Repositories expose typed methods:

```typescript
searchPois(input: { category?: string; scenario?: string; radiusKm: number; tags: string[] }): Promise<Poi[]>
getPoi(id: string): Promise<Poi>
getCouponsForPoi(poiId: string): Promise<Coupon[]>
getMenuForPoi(poiId: string): Promise<MenuItem[]>
getRouteLegs(waypoints: string[]): Promise<RouteLeg[]>
checkAvailability(input: { placeId: string; time: string; partySize: number }): Promise<AvailabilityResult>
```

- [ ] **Step 7: Run data tests**

Run: `npm run test:server -- tests/server/data-platform.test.ts`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add package.json package-lock.json lib/data scripts/seed-database.ts tests/server/data-platform.test.ts
git commit -m "feat: add PostGIS-ready local data platform"
```

### Task 8: Ranking, Filtering, Variants, And Grounded Explanations

**Files:**
- Create: `lib/planning/ranking.ts`
- Create: `lib/planning/filtering.ts`
- Create: `lib/planning/explanations.ts`
- Modify: `lib/agent/nodes/searchCandidates.ts`
- Modify: `lib/agent/nodes/rankCandidates.ts`
- Modify: `lib/agent/nodes/buildItinerary.ts`
- Create: `tests/server/ranking-filtering.test.ts`

- [ ] **Step 1: Write ranking tests**

Create tests that assert the exact detailed-design formula:

```typescript
test('scorePoi applies detailed design weights exactly', () => {
  const score = scorePoi({
    distance_score: 1,
    rating_score: 1,
    constraint_fit_score: 1,
    availability_score: 1,
    route_efficiency_score: 1,
    budget_score: 1,
    novelty_or_vibe_score: 1,
  });
  assert.equal(score, 100);

  const weighted = scorePoi({
    distance_score: 0.5,
    rating_score: 0.6,
    constraint_fit_score: 0.7,
    availability_score: 0.8,
    route_efficiency_score: 0.9,
    budget_score: 1,
    novelty_or_vibe_score: 0.4,
  });
  assert.equal(weighted, Math.round((0.22 * 0.5 + 0.18 * 0.6 + 0.16 * 0.7 + 0.14 * 0.8 + 0.12 * 0.9 + 0.10 * 1 + 0.08 * 0.4) * 100));
});

test('hardFilter removes closed, too far, wrong age, capacity mismatch, and excessive wait candidates', () => {
  const kept = hardFilterCandidates(makeFilterFixture(), {
    date: '2026-05-09',
    time: '14:00',
    radiusKm: 5,
    childAges: [5],
    partySize: 3,
    maxWaitMinutes: 15,
  });

  assert.deepEqual(kept.map((poi) => poi.id), ['poi_good']);
  assert.deepEqual(kept.rejected.map((item) => item.reason), [
    'closed_at_requested_time',
    'outside_radius',
    'age_mismatch',
    'capacity_mismatch',
    'wait_exceeds_threshold',
  ]);
});

test('buildVariants produces different main, budget, comfort, and child-first plans', () => {
  const variants = buildVariants(makeRankedFixture(), makeFamilyConstraints());
  assert.deepEqual(variants.map((variant) => variant.kind), ['main', 'budget', 'comfort', 'child_first']);
  assert.notDeepEqual(variants[0].itinerary.map((step) => step.place_id), variants[1].itinerary.map((step) => step.place_id));
  assert.ok(variants[1].estimated_budget < variants[0].estimated_budget);
});
```

- [ ] **Step 2: Run tests to verify failure**

Run: `npm run test:server -- tests/server/ranking-filtering.test.ts`

Expected: FAIL because ranking modules do not exist.

- [ ] **Step 3: Implement hard filters**

`hardFilterCandidates` must reject candidates with reason codes:

```typescript
closed_at_requested_time
outside_radius
age_mismatch
capacity_mismatch
wait_exceeds_threshold
```

Return both `kept` and `rejected` so UI can show “被筛掉原因”.

- [ ] **Step 4: Implement weighted scoring**

Use:

```typescript
score =
  0.22 * distance_score +
  0.18 * rating_score +
  0.16 * constraint_fit_score +
  0.14 * availability_score +
  0.12 * route_efficiency_score +
  0.10 * budget_score +
  0.08 * novelty_or_vibe_score
```

Return integer score `0..100` plus raw factors.

- [ ] **Step 5: Implement explanations**

`explanations.ts` returns:

```typescript
{
  top_reasons: string[],
  tradeoffs: string[],
  rejected_reasons: { place_id: string; name: string; reason: string }[]
}
```

Every string must be derived from POI facts, score factors, route legs, menu data, coupon data, or availability data.

- [ ] **Step 6: Wire graph nodes**

Update search/ranking/build nodes to pass kept, rejected, factor scores, constraint fit, and variants into `PlanResponseSchema`.

- [ ] **Step 7: Run ranking and API tests**

Run: `npm run test:server -- tests/server/ranking-filtering.test.ts`

Expected: PASS.

Run: `npm run test:server`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add lib/planning lib/agent/nodes/searchCandidates.ts lib/agent/nodes/rankCandidates.ts lib/agent/nodes/buildItinerary.ts tests/server/ranking-filtering.test.ts
git commit -m "feat: implement detailed ranking and variant logic"
```

### Task 9: Planner UI Full Workbench

**Files:**
- Create: `components/planner/PromptComposer.tsx`
- Create: `components/planner/ConstraintCards.tsx`
- Create: `components/planner/PlanCanvas.tsx`
- Create: `components/planner/VariantTabs.tsx`
- Create: `components/planner/BottomExecutionBar.tsx`
- Create: `components/planner/RecoveryDiff.tsx`
- Create: `components/planner/RejectedReasons.tsx`
- Modify: `components/PlannerView.jsx`
- Modify: `app/globals.css`
- Create: `tests/frontend/planner-workbench.test.tsx`

- [ ] **Step 1: Write workbench tests**

Tests assert visible surface:

```typescript
test('planner workbench renders input, constraints, trace, plan canvas, map, and bottom execution bar', () => {
  const html = renderPlannerWorkbench(makePlanResponseFixture());
  assert.match(html, /今天下午/);
  assert.match(html, /人群/);
  assert.match(html, /Agent 执行轨迹/);
  assert.match(html, /主方案/);
  assert.match(html, /地图与路线/);
  assert.match(html, /确认执行/);
});

test('constraint cards render as editable controls', () => {
  const html = renderConstraintCards(makePlanResponseFixture().constraints);
  assert.match(html, /data-constraint="radius_km"/);
  assert.match(html, /data-constraint="budget_level"/);
  assert.match(html, /data-constraint="start"/);
  assert.match(html, /data-constraint="diet"/);
});

test('bottom execution bar lists six detailed design actions', () => {
  const html = renderBottomExecutionBar(makePlanResponseFixture().plan.actions);
  for (const label of ['预约活动', '预订餐厅', '领取团购券', '创建点单', '发送计划', '创建日历']) {
    assert.match(html, new RegExp(label));
  }
});
```

- [ ] **Step 2: Run tests to verify failure**

Run: `npm run test:frontend -- tests/frontend/planner-workbench.test.tsx`

Expected: FAIL because focused components do not exist.

- [ ] **Step 3: Build focused components**

Move Planner rendering out of `components/PlannerView.jsx` into the new files. `PlannerView.jsx` becomes a thin wrapper until it is renamed to `.tsx`.

- [ ] **Step 4: Implement editable constraint controls**

`ConstraintCards` must call `patchConstraints(planId, updates)` for:

```text
radius_km: 3 / 5 / 10
budget_level: low / medium / high
start: HH:mm
diet: low_fat / low_sugar / vegetarian / no_gluten
transport: walk_taxi / taxi / walk
```

- [ ] **Step 5: Implement variant tabs**

Tabs show `main`, `budget`, `comfort`, and `child_first` from the API. Each tab renders its own itinerary, score, budget, tradeoffs, and route summary.

- [ ] **Step 6: Implement rejected reasons**

Render rejected candidates grouped by reason code with user-facing Chinese explanations.

- [ ] **Step 7: Implement bottom confirmation bar and mobile layout**

CSS requirements:

```css
.bottom-execution-bar {
  position: sticky;
  bottom: 0;
  z-index: 20;
}

@media (max-width: 820px) {
  .planner-workbench {
    display: grid;
    grid-template-rows: auto 1fr auto;
  }
  .map-panel {
    display: none;
  }
  .route-summary-mobile {
    display: block;
  }
}
```

- [ ] **Step 8: Run tests and build**

Run: `npm run test:frontend`

Expected: PASS.

Run: `npm run build`

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add components/planner components/PlannerView.jsx app/globals.css tests/frontend/planner-workbench.test.tsx
git commit -m "feat: build full planner workbench UI"
```

### Task 10: Trace Panel And Tool-Call Inspector

**Files:**
- Create: `components/trace/TracePanel.tsx`
- Create: `components/trace/ToolCallDetails.tsx`
- Modify: `components/planner/PlanCanvas.tsx`
- Modify: `lib/observability/tracing.ts`
- Create: `tests/frontend/trace-panel.test.tsx`
- Create: `tests/server/tracing.test.ts`

- [ ] **Step 1: Write trace tests**

Trace UI must show user-readable state plus expandable JSON:

```typescript
test('trace panel renders readable steps and expandable tool IO', () => {
  const html = renderTracePanel({
    trace: [
      { agent: 'IntentParserAgent', tool: 'parse_user_goal', status: 'ok', message: '正在理解你的约束', input_summary: { goal_length: 42 }, output_summary: { scenario: 'family' }, duration_ms: 140 },
    ],
    tool_calls: [
      { tool: 'check_availability', input_summary: { place_id: 'r_014', time: '18:00', party_size: 3 }, output_summary: { available: true, slot: '18:10' }, status: 'ok', duration_ms: 90, side_effect: false },
    ],
  });

  assert.match(html, /正在理解你的约束/);
  assert.match(html, /check_availability/);
  assert.match(html, /"place_id":"r_014"/);
  assert.match(html, /"available":true/);
});
```

- [ ] **Step 2: Run trace tests to verify failure**

Run: `npm run test:frontend -- tests/frontend/trace-panel.test.tsx`

Expected: FAIL because trace components do not exist.

- [ ] **Step 3: Implement normalized trace model**

`lib/observability/tracing.ts` must normalize LangGraph node traces, OpenAI Agent traces, tool calls, retries, failures, and side-effect IDs into one frontend shape.

- [ ] **Step 4: Implement expandable UI**

Every trace item has:

```text
user-facing message
agent name
tool name
status
duration
input JSON
output JSON
error JSON when present
side-effect badge when true
```

- [ ] **Step 5: Run tests**

Run: `npm run test:frontend`

Expected: PASS.

Run: `npm run test:server`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add components/trace lib/observability/tracing.ts components/planner/PlanCanvas.tsx tests/frontend/trace-panel.test.tsx tests/server/tracing.test.ts
git commit -m "feat: add expandable Agent trace inspector"
```

### Task 11: Mapbox Route Layer And Route Provider

**Files:**
- Modify: `package.json`
- Create: `lib/routing/routeProvider.ts`
- Create: `lib/routing/localRouteProvider.ts`
- Create: `lib/routing/externalRouteProvider.ts`
- Create: `components/map/RouteMap.tsx`
- Modify: `components/RoutePreview.jsx`
- Create: `tests/server/route-provider.test.ts`
- Create: `tests/frontend/route-map.test.tsx`

- [ ] **Step 1: Write route tests**

```typescript
test('local route provider returns legs, total minutes, walking distance, and map polyline', async () => {
  const result = await localRouteProvider.optimize({
    origin: { lat: 38.2601, lng: 140.8824 },
    waypoints: [
      { id: 'a_021', lat: 38.261, lng: 140.881 },
      { id: 'r_014', lat: 38.262, lng: 140.882 },
    ],
    mode: 'walk_taxi',
  });

  assert.ok(result.total_travel_minutes > 0);
  assert.ok(result.legs.length >= 1);
  assert.ok(result.polyline.coordinates.length >= 2);
});

test('route map renders deterministic fallback when map token is missing', () => {
  const html = renderRouteMap(makeRouteFixture(), { mapboxToken: '' });
  assert.match(html, /地图与路线/);
  assert.match(html, /data-map-fallback="true"/);
});
```

- [ ] **Step 2: Run tests to verify failure**

Run: `npm run test:server -- tests/server/route-provider.test.ts`

Expected: FAIL.

- [ ] **Step 3: Install Mapbox GL**

Run: `npm install mapbox-gl`

Expected: dependency is added.

- [ ] **Step 4: Implement route provider interface**

Provider output:

```typescript
{
  legs: RouteLeg[];
  total_travel_minutes: number;
  walking_distance_km: number;
  drive_time_minutes: number;
  polyline: { type: 'LineString'; coordinates: [number, number][] };
  provider: 'local' | 'amap' | 'google';
}
```

- [ ] **Step 5: Implement Map component**

`RouteMap` uses Mapbox when `NEXT_PUBLIC_MAPBOX_TOKEN` exists and renders a deterministic SVG/CSS route fallback when absent. The fallback must use real route coordinates from API response, not hardcoded decorative pins.

- [ ] **Step 6: Wire graph route node**

`optimize_route` tool returns route provider output and all map data is exposed in the plan response.

- [ ] **Step 7: Run tests**

Run: `npm run test:server -- tests/server/route-provider.test.ts`

Expected: PASS.

Run: `npm run test:frontend -- tests/frontend/route-map.test.tsx`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add package.json package-lock.json lib/routing components/map components/RoutePreview.jsx tests/server/route-provider.test.ts tests/frontend/route-map.test.tsx
git commit -m "feat: add route provider and map view"
```

### Task 12: Full Recovery Strategy Matrix

**Files:**
- Create: `lib/recovery/recoveryPolicies.ts`
- Create: `lib/recovery/recoveryDiff.ts`
- Modify: `lib/agent/nodes/recoverPlan.ts`
- Modify: `lib/agent/graph.ts`
- Create: `tests/server/recovery-matrix.test.ts`

- [ ] **Step 1: Write recovery matrix tests**

```typescript
test('restaurant unavailable replaces only restaurant and preserves activity and dessert walk', async () => {
  const recovered = await recoverFixture('restaurant_unavailable');
  assert.equal(recovered.diff.changed, 'restaurant');
  assert.deepEqual(recovered.diff.preserved, ['亲子科学馆', '河畔低糖甜品散步']);
});

test('activity full replaces activity and keeps restaurant when still valid', async () => {
  const recovered = await recoverFixture('activity_full');
  assert.equal(recovered.diff.changed, 'activity');
  assert.ok(recovered.diff.preserved.includes('绿荫轻食餐厅'));
});

test('rain switches outdoor nodes to indoor and marks rainy plan', async () => {
  const recovered = await recoverFixture('rain');
  assert.equal(recovered.plan.badges.includes('雨天方案'), true);
  assert.equal(recovered.plan.itinerary.some((step) => step.risk.includes('户外下雨')), false);
});

test('route timeout removes low priority node and exposes deleted reason', async () => {
  const recovered = await recoverFixture('route_timeout');
  assert.equal(recovered.diff.changed, 'route');
  assert.ok(recovered.diff.removed.some((item) => item.reason === 'route_timeout_low_priority'));
});

test('budget overrun returns cheaper version with coupon or lower price POI', async () => {
  const recovered = await recoverFixture('budget_overrun');
  assert.equal(recovered.diff.changed, 'budget');
  assert.ok(recovered.plan.overview.estimated_budget_value < recovered.previous.overview.estimated_budget_value);
});

test('constraint conflict returns healthy and relaxed alternatives', async () => {
  const recovered = await recoverFixture('constraint_conflict');
  assert.deepEqual(recovered.alternatives.map((item) => item.kind), ['healthy', 'relaxed']);
});

test('tool timeout retries once then falls back with visible retry trace', async () => {
  const recovered = await recoverFixture('tool_timeout');
  assert.equal(recovered.trace.some((step) => step.status === 'retrying'), true);
  assert.equal(recovered.trace.some((step) => step.status === 'fallback'), true);
});
```

- [ ] **Step 2: Run tests to verify failure**

Run: `npm run test:server -- tests/server/recovery-matrix.test.ts`

Expected: FAIL because only restaurant recovery exists.

- [ ] **Step 3: Implement policies**

`recoveryPolicies.ts` must define handlers for:

```text
restaurant_unavailable
activity_full
rain
route_timeout
budget_overrun
constraint_conflict
tool_timeout
```

- [ ] **Step 4: Correct preserved-node logic**

For restaurant recovery, `preserved` must include stable non-restaurant itinerary nodes, not the transport node or new restaurant.

- [ ] **Step 5: Wire graph failure edges**

`VALIDATE_PLAN` and `EXECUTE_ACTIONS` route to `RECOVERY` when validation issues or tool failures exist. Recovery returns to `BUILD_ITINERARY` or `USER_CONFIRMATION` depending on whether user approval is required.

- [ ] **Step 6: Run recovery tests**

Run: `npm run test:server -- tests/server/recovery-matrix.test.ts`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add lib/recovery lib/agent/nodes/recoverPlan.ts lib/agent/graph.ts tests/server/recovery-matrix.test.ts
git commit -m "feat: implement full recovery strategy matrix"
```

### Task 13: MCP-Ready Tool Adapters And Execution Receipts

**Files:**
- Create: `lib/tools/toolRegistry.ts`
- Create: `lib/tools/parseUserGoal.ts`
- Create: `lib/tools/getWeather.ts`
- Create: `lib/tools/searchPlaces.ts`
- Create: `lib/tools/searchRestaurants.ts`
- Create: `lib/tools/checkAvailability.ts`
- Create: `lib/tools/optimizeRoute.ts`
- Create: `lib/tools/buildItinerary.ts`
- Create: `lib/tools/validatePlan.ts`
- Create: `lib/tools/compareAlternatives.ts`
- Create: `lib/tools/reserveActivity.ts`
- Create: `lib/tools/createReservation.ts`
- Create: `lib/tools/claimCoupon.ts`
- Create: `lib/tools/createOrder.ts`
- Create: `lib/tools/sendPlanMessage.ts`
- Create: `lib/tools/createCalendarEvent.ts`
- Create: `tests/server/tool-registry.test.ts`

- [ ] **Step 1: Write tool registry tests**

```typescript
test('tool registry exposes all fifteen detailed design tools with side effect metadata', () => {
  const tools = toolRegistry.schemas();
  assert.deepEqual(tools.map((tool) => tool.name), [
    'parse_user_goal',
    'get_weather',
    'search_places',
    'search_restaurants',
    'check_availability',
    'optimize_route',
    'build_itinerary',
    'validate_plan',
    'compare_alternatives',
    'reserve_activity',
    'create_reservation',
    'claim_coupon',
    'create_order',
    'send_plan_message',
    'create_calendar_event',
  ]);
  assert.deepEqual(
    tools.filter((tool) => tool.side_effect).map((tool) => tool.name),
    ['reserve_activity', 'create_reservation', 'claim_coupon', 'create_order', 'send_plan_message', 'create_calendar_event'],
  );
});

test('side-effect tools return realistic typed receipt payloads', async () => {
  const receipts = await executeAllConfirmedActions(makeSixActionFixture(), { confirmed: true, idempotencyKey: 'idem_001' });
  assert.deepEqual(receipts.map((receipt) => receipt.id.slice(0, 3)), ['TKT', 'RES', 'CPN', 'ORD', 'MSG', 'CAL']);
  assert.ok(receipts.find((receipt) => receipt.tool === 'claim_coupon')?.payload.rules.includes('退款'));
  assert.ok(receipts.find((receipt) => receipt.tool === 'create_order')?.payload.items.length >= 1);
});
```

- [ ] **Step 2: Run tests to verify failure**

Run: `npm run test:server -- tests/server/tool-registry.test.ts`

Expected: FAIL because TypeScript tool adapters do not exist.

- [ ] **Step 3: Implement tool registry**

Every tool schema includes:

```typescript
{
  name: string;
  input_schema: JsonSchema;
  output_schema: JsonSchema;
  side_effect: boolean;
  requires_confirmation: boolean;
}
```

- [ ] **Step 4: Implement read-only tools**

Read-only tools must use repositories and return traceable inputs/outputs:

```text
parse_user_goal
get_weather
search_places
search_restaurants
check_availability
optimize_route
build_itinerary
validate_plan
compare_alternatives
```

- [ ] **Step 5: Implement side-effect adapters with idempotency**

Side-effect tools must require:

```text
confirmed=true
idempotency_key
human_confirmation_snapshot
```

Return receipt IDs and payload details.

- [ ] **Step 6: Run tests**

Run: `npm run test:server -- tests/server/tool-registry.test.ts`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add lib/tools tests/server/tool-registry.test.ts
git commit -m "feat: add MCP-ready tool adapters"
```

### Task 14: Guardrails, Privacy, And Confirmation UX

**Files:**
- Create: `lib/agent/guardrails.ts`
- Create: `lib/privacy/redaction.ts`
- Create: `components/planner/ConfirmationDialog.tsx`
- Modify: `components/planner/BottomExecutionBar.tsx`
- Modify: `lib/agent/nodes/executeActions.ts`
- Modify: `lib/tools/toolRegistry.ts`
- Create: `tests/server/guardrails.test.ts`
- Create: `tests/frontend/confirmation-dialog.test.tsx`

- [ ] **Step 1: Write guardrail tests**

```typescript
test('guardrails block hallucinated place ids', () => {
  assert.throws(
    () => ensureKnownPlaceIds({ itinerary: [{ place_id: 'invented_001' }] }, new Set(['r_014'])),
    /unknown_place_id:invented_001/,
  );
});

test('side effects require confirmation snapshot', async () => {
  await assert.rejects(
    () => executeActionsNode(makeExecutionState(), { confirmed: true, confirmationSnapshot: null }),
    /confirmation_snapshot_required/,
  );
});

test('privacy redaction removes phone, email, precise address, and raw contact identifiers', () => {
  const redacted = redactPrivateText('发给 xiaoran@example.com，手机号 13812345678，地址 青叶区一番町1-2-3');
  assert.equal(redacted.includes('xiaoran@example.com'), false);
  assert.equal(redacted.includes('13812345678'), false);
  assert.equal(redacted.includes('一番町1-2-3'), false);
});
```

- [ ] **Step 2: Write confirmation dialog tests**

```typescript
test('confirmation dialog shows concrete sensitive action details before execution', () => {
  const html = renderConfirmationDialog(makeSixActionFixture());
  assert.match(html, /将为 3 人预订/);
  assert.match(html, /手机号尾号/);
  assert.match(html, /团购券价格/);
  assert.match(html, /退款规则/);
  assert.match(html, /发送对象/);
  assert.match(html, /日历参与人/);
});
```

- [ ] **Step 3: Run tests to verify failure**

Run: `npm run test:server -- tests/server/guardrails.test.ts`

Expected: FAIL.

Run: `npm run test:frontend -- tests/frontend/confirmation-dialog.test.tsx`

Expected: FAIL.

- [ ] **Step 4: Implement guardrails**

Guardrails must enforce:

```text
known_place_ids_only
no_unconfirmed_side_effects
no_payment_without_user_redirect
no_raw_private_contact_in_trace
message_content_visible_before_send
calendar_participants_visible_before_create
coupon_price_rules_visible_before_claim
order_items_pickup_visible_before_create
```

- [ ] **Step 5: Implement confirmation dialog**

Dialog displays all six action categories and must create a `confirmationSnapshot` object sent to `/execute`:

```typescript
{
  confirmed_at: string;
  visible_actions: PlanAction[];
  visible_message_content: string;
  visible_coupon_rules: string[];
  visible_order_items: MenuItem[];
  phone_tail: string;
}
```

- [ ] **Step 6: Run tests**

Run: `npm run test:server -- tests/server/guardrails.test.ts`

Expected: PASS.

Run: `npm run test:frontend -- tests/frontend/confirmation-dialog.test.tsx`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add lib/agent/guardrails.ts lib/privacy/redaction.ts components/planner/ConfirmationDialog.tsx components/planner/BottomExecutionBar.tsx lib/agent/nodes/executeActions.ts lib/tools/toolRegistry.ts tests/server/guardrails.test.ts tests/frontend/confirmation-dialog.test.tsx
git commit -m "feat: enforce guardrails and concrete confirmations"
```

### Task 15: Commercial Loop UI And Receipts

**Files:**
- Create: `components/planner/ReceiptStack.tsx`
- Create: `components/planner/CommercialActions.tsx`
- Modify: `components/planner/BottomExecutionBar.tsx`
- Modify: `components/planner/PlanCanvas.tsx`
- Create: `tests/frontend/commercial-loop.test.tsx`

- [ ] **Step 1: Write commercial loop tests**

```typescript
test('commercial action UI shows reservation, activity, coupon, order, message, and calendar', () => {
  const html = renderCommercialActions(makeSixActionFixture());
  for (const label of ['活动预约', '餐厅订座', '团购券', '点单', '发送计划', '日历']) {
    assert.match(html, new RegExp(label));
  }
});

test('receipt stack renders all machine-verifiable receipt ids', () => {
  const html = renderReceiptStack(makeSixReceiptFixture());
  for (const prefix of ['TKT-', 'RES-', 'CPN-', 'ORD-', 'MSG-', 'CAL-']) {
    assert.match(html, new RegExp(prefix));
  }
});
```

- [ ] **Step 2: Run tests to verify failure**

Run: `npm run test:frontend -- tests/frontend/commercial-loop.test.tsx`

Expected: FAIL because components do not exist.

- [ ] **Step 3: Implement action and receipt components**

`CommercialActions` renders pending actions before confirmation. `ReceiptStack` renders machine-verifiable output after execution with `id`, `status`, `tool`, `detail`, and payload summary.

- [ ] **Step 4: Wire into Planner**

The Planner must never show “已帮你订好” without receipt IDs. It must show `reservation_id`, `ticket_id`, `coupon_id`, `order_id`, `message_id`, and `event_id` after execution.

- [ ] **Step 5: Run tests**

Run: `npm run test:frontend`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add components/planner/ReceiptStack.tsx components/planner/CommercialActions.tsx components/planner/BottomExecutionBar.tsx components/planner/PlanCanvas.tsx tests/frontend/commercial-loop.test.tsx
git commit -m "feat: expose full commercial execution loop"
```

### Task 16: Remove Main-Path Mock Agent And Legacy Drift

**Files:**
- Modify: `features/planner/mockAgent.js`
- Modify: `src/agent.mjs`
- Modify: `tests/agent.test.mjs`
- Create: `tests/fixtures/legacyMockAgent.mjs`
- Modify: `README.md`
- Modify: `design_submission.md`

- [ ] **Step 1: Write drift tests**

Create a test that scans product imports:

```typescript
test('product source does not import legacy mock agent on the main path', async () => {
  const files = await sourceFiles(['app', 'components', 'features']);
  const offenders = files.filter((file) => file.content.includes("from '@/src/agent.mjs'") || file.content.includes("from '../src/agent.mjs'"));
  assert.deepEqual(offenders.map((file) => file.path), []);
});
```

- [ ] **Step 2: Run drift test to verify failure**

Run: `npm run test:frontend -- tests/frontend/no-main-path-mock.test.ts`

Expected: FAIL if any product file still imports `src/agent.mjs`.

- [ ] **Step 3: Move mock to fixtures**

Keep old mock only under `tests/fixtures/legacyMockAgent.mjs` for historical tests. Update `tests/agent.test.mjs` to import the fixture or delete obsolete tests after contract/API tests cover the same behavior.

- [ ] **Step 4: Update docs**

README and submission docs must state:

```text
主体验通过 Next.js API + LangGraph workflow + MCP-ready tools 运行。
Python backend 是迁移前的参考实现，不是主演示路径。
```

- [ ] **Step 5: Run tests**

Run: `npm run test:all`

Expected: PASS.

Run: `npm run build`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add features/planner/mockAgent.js src/agent.mjs tests/agent.test.mjs tests/fixtures/legacyMockAgent.mjs README.md design_submission.md tests/frontend/no-main-path-mock.test.ts
git commit -m "chore: remove mock agent from main product path"
```

### Task 17: End-To-End Demo, Desktop, Mobile, And Performance

**Files:**
- Modify: `package.json`
- Create: `tests/e2e/weekendpilot.spec.ts`
- Create: `tests/e2e/mobile.spec.ts`
- Create: `tests/e2e/performance.spec.ts`
- Create: `docs/demo_script.md`

- [ ] **Step 1: Install Playwright**

Run: `npm install -D @playwright/test`

Expected: dependency is added.

- [ ] **Step 2: Add E2E scripts**

Modify `package.json`:

```json
{
  "test:e2e": "playwright test tests/e2e",
  "test:all": "npm test && npm run test:contracts && npm run test:server && npm run test:frontend && npm run test:e2e"
}
```

- [ ] **Step 3: Write desktop E2E test**

Test the three-act demo:

```typescript
test('desktop demo completes plan, execution, and recovery', async ({ page }) => {
  await page.goto('http://127.0.0.1:4173');
  await page.getByRole('textbox').fill('今天下午是空的，想和老婆孩子出去玩几个小时，别离家太远。孩子 5 岁，老婆最近在减脂，帮我安排一下。');
  await page.getByRole('button', { name: '生成计划' }).click();
  await expect(page.getByText('已理解你的需求')).toBeVisible();
  await expect(page.getByText('Agent 执行轨迹')).toBeVisible();
  await expect(page.getByText('地图与路线')).toBeVisible();
  await page.getByRole('button', { name: '确认执行' }).click();
  await expect(page.getByText(/RES-/)).toBeVisible();
  await expect(page.getByText(/CPN-/)).toBeVisible();
  await page.getByRole('button', { name: '模拟餐厅无位' }).click();
  await expect(page.getByText('重新确认执行')).toBeVisible();
});
```

- [ ] **Step 4: Write mobile E2E test**

Mobile viewport must show input/status, horizontal timeline, and bottom execution:

```typescript
test.use({ viewport: { width: 390, height: 844 } });

test('mobile layout uses three-stage planner and collapsed map summary', async ({ page }) => {
  await page.goto('http://127.0.0.1:4173');
  await page.getByRole('button', { name: '家庭半日' }).click();
  await expect(page.getByTestId('mobile-route-summary')).toBeVisible();
  await expect(page.getByTestId('bottom-execution-bar')).toBeVisible();
  await expect(page.getByTestId('desktop-map-panel')).toBeHidden();
});
```

- [ ] **Step 5: Write performance test**

```typescript
test('first complete plan appears within 10 seconds', async ({ page }) => {
  await page.goto('http://127.0.0.1:4173');
  const start = Date.now();
  await page.getByRole('button', { name: '家庭半日' }).click();
  await expect(page.getByText('主方案')).toBeVisible({ timeout: 10000 });
  assert.ok(Date.now() - start < 10000);
});
```

- [ ] **Step 6: Run E2E tests**

Run: `npm run dev`

Expected: local server listens on `http://127.0.0.1:4173`.

Run in another terminal: `npm run test:e2e`

Expected: PASS.

- [ ] **Step 7: Write demo script**

`docs/demo_script.md` must include the three acts:

```text
第一幕：一句话到完整计划
第二幕：计划到执行回执
第三幕：餐厅无位、雨天、活动满员任选一个失败恢复
```

Include exact clicks and expected screen text.

- [ ] **Step 8: Commit**

```bash
git add package.json package-lock.json tests/e2e docs/demo_script.md
git commit -m "test: add end-to-end demo verification"
```

### Task 18: Observability, Checkpoint Persistence, And Legacy Closure

**Files:**
- Create: `lib/observability/otel.ts`
- Modify: `lib/observability/tracing.ts`
- Modify: `lib/data/repositories/traceRepository.ts`
- Modify: `lib/data/repositories/checkpointRepository.ts`
- Modify: `backend/README.md`
- Modify: `docs/detailed_design_gap_analysis.md`
- Create: `docs/final_alignment_report.md`
- Create: `tests/server/observability-persistence.test.ts`

- [ ] **Step 1: Write observability and persistence tests**

```typescript
test('checkpoint repository can persist and reload graph state by thread id', async () => {
  const repo = createTestCheckpointRepository();
  await repo.save({ thread_id: 'thread_001', status: 'USER_CONFIRMATION', state_json: { pending_actions: [1, 2, 3] } });
  const loaded = await repo.load('thread_001');
  assert.equal(loaded.status, 'USER_CONFIRMATION');
  assert.deepEqual(loaded.state_json.pending_actions, [1, 2, 3]);
});

test('trace repository stores tool logs, retry logs, and receipt ids', async () => {
  const repo = createTestTraceRepository();
  await repo.append('plan_001', { tool: 'create_reservation', status: 'ok', side_effect: true, output_summary: { id: 'RES-1' } });
  const trace = await repo.list('plan_001');
  assert.equal(trace[0].output_summary.id, 'RES-1');
});
```

- [ ] **Step 2: Run tests to verify failure**

Run: `npm run test:server -- tests/server/observability-persistence.test.ts`

Expected: FAIL until repositories are implemented.

- [ ] **Step 3: Implement OpenTelemetry boundary**

`lib/observability/otel.ts` exports:

```typescript
export function startWeekendPilotTelemetry() {}
export function createSpan(name: string, attributes: Record<string, unknown>) {}
export function recordToolCall(spanName: string, payload: ToolCall) {}
```

Use no-op implementations when OTEL env vars are absent.

- [ ] **Step 4: Persist checkpoints and traces**

Graph checkpointer writes each super-step to `checkpoints`. Trace normalization writes `traces` and `executions` rows. Use repository interfaces so local JSON tests and PostgreSQL runtime share behavior.

- [ ] **Step 5: Update legacy docs**

`backend/README.md` must say:

```text
This Python backend is retained as a legacy reference for the earlier local demo. The production demo path is the Next.js TypeScript API and LangGraph workflow.
```

`docs/detailed_design_gap_analysis.md` becomes a closure report with:

```text
closed
partially closed
accepted remaining risk
verification command
```

- [ ] **Step 6: Create final report**

`docs/final_alignment_report.md` must list every section of `detailed_design.md` and link the implemented files/tests that satisfy it.

- [ ] **Step 7: Run all verification**

Run: `npm run test:all`

Expected: PASS.

Run: `uv run pytest tests/backend`

Expected: PASS, or documented as legacy reference if Python tests are intentionally frozen.

Run: `npm run build`

Expected: PASS.

Run: `git status --short`

Expected: only intentional changed files before final commit.

- [ ] **Step 8: Commit**

```bash
git add lib/observability lib/data/repositories backend/README.md docs/detailed_design_gap_analysis.md docs/final_alignment_report.md tests/server/observability-persistence.test.ts
git commit -m "docs: close detailed design alignment"
```

## Final Verification Checklist

- [ ] `npm run test:all` passes.
- [ ] `uv run pytest tests/backend` passes or Python legacy status is documented in `backend/README.md`.
- [ ] `npm run build` passes.
- [ ] The Planner UI no longer imports `src/agent.mjs` or uses `features/planner/mockAgent.js` for main execution.
- [ ] `/api/tool-schemas` returns 15 tools.
- [ ] `/api/plans/build` returns constraints, trace, tool calls, itinerary, variants, rejected reasons, route map data, and six pending actions.
- [ ] `/api/plans/{id}/execute` rejects without confirmation snapshot.
- [ ] `/api/plans/{id}/execute` returns TKT, RES, CPN, ORD, MSG, and CAL receipts after confirmation.
- [ ] `/api/plans/{id}/recover` supports restaurant unavailable, activity full, rain, route timeout, budget overrun, constraint conflict, and tool timeout.
- [ ] Desktop flow shows input, editable constraints, trace inspector, plan canvas, route map, variant tabs, bottom execution bar, confirmation dialog, receipts, and recovery diff.
- [ ] Mobile flow shows top input/status, timeline cards, collapsed route summary, and sticky bottom execution.
- [ ] No travel-longform examples remain in the primary UI.
- [ ] No raw phone, email, exact home address, or unconfirmed contact message is stored in trace.
- [ ] `docs/final_alignment_report.md` maps all 20 detailed-design sections to code and tests.

## Self-Review

Spec coverage: all 20 sections of `detailed_design.md` are mapped in the coverage matrix and task list.

Placeholder scan: this plan contains no open-ended implementation placeholders. Every task has concrete files, tests, commands, expected results, and commit scope.

Type consistency: canonical names are `ParsedConstraints`, `Poi`, `PlanResponse`, `PlanAction`, `Receipt`, `RecoveryDiff`, `ToolCall`, and `PlanStatuses`; later tasks refer to the same names.

