# Minimal Demo Deliverables Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable hackathon demo and concise submission package for WeekendPilot.

**Architecture:** Keep the existing research documents and prototype images as internal material. Add a dependency-free static web demo powered by deterministic JavaScript mock tools, plus a two-page submission document and README. The demo shows the full loop: natural-language goal, constraints, tool trace, itinerary, confirmation receipts, and failure recovery.

**Tech Stack:** HTML, CSS, browser JavaScript, Node.js built-in test runner for behavior tests.

---

### Task 1: Test Harness And Agent Contract

**Files:**
- Create: `package.json`
- Create: `tests/agent.test.mjs`
- Create: `src/agent.mjs`

- [ ] **Step 1: Write failing tests**

Create tests for the required demo behaviors:

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildPlan,
  executePlan,
  recoverUnavailableRestaurant,
  demoTools
} from '../src/agent.mjs';

test('buildPlan extracts family constraints and returns trace plus itinerary', () => {
  const result = buildPlan('Today afternoon is free, I want to go out with my wife and 5yo kid, not too far, wife is on a diet.');

  assert.equal(result.constraints.party, '2 adults, 1 child (5yo)');
  assert.equal(result.constraints.dietary, 'low-fat');
  assert.equal(result.constraints.radiusKm, 5);
  assert.ok(result.trace.some((step) => step.tool === 'parse_user_goal'));
  assert.ok(result.trace.some((step) => step.tool === 'check_availability'));
  assert.equal(result.itinerary.length, 3);
  assert.equal(result.plan.status, 'ready_for_confirmation');
});

test('executePlan returns visible mock receipts for side-effect tools', () => {
  const result = executePlan(buildPlan('family low fat nearby').plan);

  assert.deepEqual(result.map((receipt) => receipt.type), [
    'activity_reservation',
    'restaurant_reservation',
    'message'
  ]);
  assert.match(result[0].id, /^TKT-/);
  assert.match(result[1].id, /^RES-/);
  assert.match(result[2].id, /^MSG-/);
});

test('recoverUnavailableRestaurant swaps only the restaurant and records a diff', () => {
  const original = buildPlan('family low fat nearby').plan;
  const recovered = recoverUnavailableRestaurant(original);

  assert.equal(recovered.diff.changed, 'restaurant');
  assert.equal(recovered.itinerary[0].placeId, original.itinerary[0].placeId);
  assert.notEqual(recovered.itinerary[1].placeId, original.itinerary[1].placeId);
  assert.equal(recovered.status, 'recovered_pending_confirmation');
});

test('demoTools lists the eight mock tools promised in the submission', () => {
  assert.deepEqual(demoTools, [
    'parse_user_goal',
    'search_places',
    'search_restaurants',
    'rank_candidates',
    'optimize_route',
    'check_availability',
    'create_reservation',
    'send_plan_message'
  ]);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`

Expected: FAIL because `src/agent.mjs` has not implemented the exports.

- [ ] **Step 3: Implement minimal agent functions**

Implement `buildPlan`, `executePlan`, `recoverUnavailableRestaurant`, and `demoTools` with deterministic mock data.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test`

Expected: all tests pass.

### Task 2: Next Demo UI

**Files:**
- Create: `app/page.jsx`
- Create: `app/globals.css`
- Create: `components/*`
- Create: `features/planner/mockAgent.js`
- Create: `data/poi.json`

- [ ] **Step 1: Build the UI shell**

Create a one-screen workbench with an input area, constraint cards, tool trace, itinerary, map-style route panel, confirmation receipts, and recovery diff panel.

- [ ] **Step 2: Wire UI to agent functions**

Use `buildPlan`, `executePlan`, and `recoverUnavailableRestaurant` from `src/agent.mjs`. Buttons must demonstrate the main flow and failure recovery without network calls.

- [ ] **Step 3: Verify locally**

Run: `npm test`

Expected: tests remain green. Run `npm run dev` and open `http://127.0.0.1:4173` in a browser to run the demo.

### Task 3: Submission Documents

**Files:**
- Create: `README.md`
- Create: `design_submission.md`

- [ ] **Step 1: Write README**

README must include purpose, how to run, file map, demo script, tool list, and review-finding coverage.

- [ ] **Step 2: Write two-page submission doc**

Document must compress the long docs into product position, architecture, tool chain, safety, failure recovery, and scoring alignment.

- [ ] **Step 3: Verify no unsupported claims**

The submission must say this is a deterministic mock demo, not claim production Next.js/PostGIS implementation.

### Task 4: Final Verification

**Files:**
- Verify all created files.

- [ ] **Step 1: Run automated tests**

Run: `npm test`

Expected: all tests pass.

- [ ] **Step 2: Inspect repository state**

Run: `git status --short`

Expected: new files only, no deleted files.

- [ ] **Step 3: Check deliverable presence**

Run: `Get-ChildItem -Recurse -File | Where-Object { $_.FullName -notmatch '\\.git\\' }`

Expected: README, design submission, static demo, tests, mock data, and existing docs/images.
