import test from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { pathToFileURL } from 'node:url';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { JSDOM } from 'jsdom';

register(new URL('../css-module-loader.mjs', import.meta.url), pathToFileURL(`${process.cwd()}/`));

const { ActivityView } = await import('../../components/activity/ActivityView');
const { HomeView } = await import('../../components/HomeView');
const { PlanCard } = await import('../../components/saved/PlanCard');
const { PlanDetailPanel } = await import('../../components/saved/PlanDetailPanel');
const { PlanEditModal } = await import('../../components/saved/PlanEditModal');
const { DietSection } = await import('../../components/settings/DietSection');
const { LocationSection } = await import('../../components/settings/LocationSection');

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test('home composer gives immediate plan and voice feedback', async () => {
  const planned: string[] = [];
  const { container } = render(
    <HomeView
      goal="family half-day plan"
      isPlanning={true}
      onGoalChange={() => {}}
      onPlan={(goal: string) => planned.push(goal)}
    />,
  );

  const planButton = byTestId<HTMLButtonElement>(container, 'generate-plan-button');
  assert.equal(planButton.disabled, true);

  const before = container.textContent ?? '';
  await click(byTestId(container, 'voice-input-button'));
  assert.notEqual(container.textContent ?? '', before);
});

test('activity view filter, search, and receipt details are interactive', async () => {
  const { container } = render(<ActivityView />);

  await waitFor(() => byTestId(container, 'activity-receipt-0'));
  await click(byTestId(container, 'activity-filter-completed'));
  assert.ok(byTestId(container, 'activity-list').textContent?.length);

  const search = byTestId<HTMLInputElement>(container, 'activity-search-input');
  await inputText(search, 'movie');
  assert.equal(search.value, 'movie');

  await click(byTestId(container, 'activity-receipt-0'));
  assert.ok(byTestId(container, 'activity-receipt-panel').textContent?.length);
});

test('saved plan card, edit modal, details close, and delete callbacks are interactive', async () => {
  const plan = makePlanSummary();
  let edits = 0;
  let executions = 0;
  let deletes = 0;
  let closed = 0;
  const { container } = render(
    <>
      <PlanCard
        plan={plan}
        index={0}
        selected={false}
        onSelect={() => {}}
        onEdit={() => { edits += 1; }}
        onExecute={() => { executions += 1; }}
        onDelete={() => { deletes += 1; }}
      />
      <PlanDetailPanel plan={plan} onClose={() => { closed += 1; }} />
      <PlanEditModal plan={plan} onSave={async () => { edits += 1; }} onClose={() => { closed += 1; }} />
    </>,
  );

  await click(byTestId(container, 'plan-edit-plan_001'));
  assert.equal(edits, 1);

  assert.ok(byTestId(container, 'plan-edit-modal').textContent?.length);
  await click(byTestId(container, 'plan-edit-modal'));
  assert.equal(closed, 1);

  await click(byTestId(container, 'details-close'));
  assert.equal(closed, 2);

  await click(byTestId(container, 'plan-execute-plan_001'));
  assert.equal(executions, 1);

  await click(byTestId(container, 'plan-delete-plan_001'));
  await waitFor(() => assert.equal(deletes, 1));
});

test('settings preference toggles and radius slider update visible state', async () => {
  function SettingsHarness() {
    const [vegetarian, setVegetarian] = React.useState(false);
    const [radius, setRadius] = React.useState(5);
    return (
      <>
        <DietSection
          fitnessFriendly={true}
          vegetarian={vegetarian}
          glutenFree={false}
          onToggle={(key: string) => {
            if (key === 'vegetarian') setVegetarian((value) => !value);
          }}
        />
        <LocationSection radiusKm={radius} onChange={setRadius} />
      </>
    );
  }

  const { container } = render(<SettingsHarness />);
  const vegetarianToggle = byTestId<HTMLButtonElement>(container, 'preference-vegetarian');
  assert.equal(vegetarianToggle.getAttribute('aria-pressed'), 'false');
  await click(vegetarianToggle);
  assert.equal(vegetarianToggle.getAttribute('aria-pressed'), 'true');

  const slider = byTestId<HTMLInputElement>(container, 'radius-slider');
  await changeInput(slider, '8');
  assert.match(container.textContent ?? '', /8/);
});

function render(element: React.ReactElement) {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
    url: 'http://127.0.0.1:4174/',
  });
  globalThis.window = dom.window as unknown as Window & typeof globalThis;
  globalThis.document = dom.window.document;
  Object.defineProperty(globalThis, 'navigator', {
    configurable: true,
    value: dom.window.navigator,
  });
  globalThis.localStorage = dom.window.localStorage;
  globalThis.HTMLElement = dom.window.HTMLElement;
  globalThis.Event = dom.window.Event;
  globalThis.KeyboardEvent = dom.window.KeyboardEvent;
  globalThis.MouseEvent = dom.window.MouseEvent;
  dom.window.HTMLElement.prototype.attachEvent = () => {};
  dom.window.HTMLElement.prototype.detachEvent = () => {};

  const container = dom.window.document.getElementById('root')!;
  const root = createRoot(container);
  act(() => {
    root.render(element);
  });
  return { container, root };
}

function byTestId<T extends Element = Element>(container: Element, testId: string): T {
  const element = container.querySelector(`[data-testid="${testId}"]`);
  assert.ok(element, `Missing [data-testid="${testId}"]`);
  return element as T;
}

async function click(element: Element) {
  await act(async () => {
    element.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  });
}

async function inputText(input: HTMLInputElement, value: string) {
  await act(async () => {
    setNativeValue(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
}

async function changeInput(input: HTMLInputElement, value: string) {
  await act(async () => {
    setNativeValue(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });
}

function setNativeValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), 'value')?.set;
  setter?.call(input, value);
}

async function waitFor(assertion: () => void, timeoutMs = 2500) {
  const start = Date.now();
  let error: unknown;
  while (Date.now() - start < timeoutMs) {
    try {
      assertion();
      return;
    } catch (err) {
      error = err;
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 25));
      });
    }
  }
  throw error;
}

function makePlanSummary() {
  return {
    id: 'plan_001',
    title: 'Family science half day',
    status: 'saved',
    summary: 'Science museum and nearby cafe.',
    created_at: '2026-05-08T10:00:00Z',
    updated_at: '2026-05-08T10:30:00Z',
    tags: ['family', 'half-day'],
    location: 'city center',
    estimated_cost: '320',
    itinerary_count: 4,
  } as const;
}
