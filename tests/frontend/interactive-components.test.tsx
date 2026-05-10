import test from 'node:test';
import assert from 'node:assert/strict';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { JSDOM } from 'jsdom';

import { ActivityView } from '../../components/ActivityView';
import { AppChrome } from '../../components/AppChrome';
import { HomeView } from '../../components/HomeView';
import { SavedPlansView } from '../../components/SavedPlansView';
import { SettingsView } from '../../components/SettingsView';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test('home composer gives immediate plan and voice feedback', async () => {
  const planned: string[] = [];
  const { container } = render(
    <HomeView
      goal="家庭半日计划"
      isPlanning={true}
      onGoalChange={() => {}}
      onPlan={(goal: string) => planned.push(goal)}
    />,
  );

  const planButton = byTestId<HTMLButtonElement>(container, 'generate-plan-button');
  assert.equal(planButton.disabled, true);
  assert.match(planButton.textContent ?? '', /生成中/);

  await click(byTestId(container, 'voice-input-button'));
  assert.match(container.textContent ?? '', /当前浏览器不支持语音输入/);
});

test('app chrome search opens a real input and reports queries', async () => {
  const queries: string[] = [];
  const { container } = render(
    <AppChrome activeView="home" onNavigate={() => {}} onNewPlan={() => {}} onSearch={(query: string) => queries.push(query)}>
      <div />
    </AppChrome>,
  );

  await click(byTestId(container, 'global-search-trigger'));
  const input = byTestId<HTMLInputElement>(container, 'global-search-input');
  await inputText(input, '亲子');

  assert.equal(input.value, '亲子');
  assert.deepEqual(queries, ['亲子']);
});

test('activity view filter, search, and receipt details are interactive', async () => {
  const { container } = render(<ActivityView />);

  await click(byTestId(container, 'activity-filter-toggle'));
  assert.ok(byTestId(container, 'activity-filter-panel').textContent?.includes('全部'));

  await click(byTestId(container, 'activity-search-toggle'));
  const search = byTestId<HTMLInputElement>(container, 'activity-search-input');
  await inputText(search, '电影');
  assert.ok((container.textContent ?? '').includes('电影'));

  await click(byTestId(container, 'activity-receipt-0'));
  assert.ok(byTestId(container, 'activity-receipt-panel').textContent?.includes('查看回执'));
});

test('saved plans support list mode, menus, edit, execute, details actions, and delete', async () => {
  let executions = 0;
  const { container } = render(<SavedPlansView onPlan={() => { executions += 1; }} />);

  await click(byTestId(container, 'saved-view-list'));
  assert.ok(byTestId(container, 'saved-plans-list').className.includes('list'));

  await click(byTestId(container, 'saved-menu-family_science_half_day'));
  assert.ok(byTestId(container, 'saved-menu-panel').textContent?.includes('复制计划'));

  await click(byTestId(container, 'saved-edit-family_science_half_day'));
  assert.ok(byTestId(container, 'saved-edit-panel').textContent?.includes('编辑计划'));

  await click(byTestId(container, 'saved-execute-family_science_half_day'));
  assert.equal(executions, 1);

  await click(byTestId(container, 'saved-share'));
  assert.match(container.textContent ?? '', /已准备分享文案/);

  await click(byTestId(container, 'saved-copy'));
  assert.match(container.textContent ?? '', /已复制计划摘要/);

  await click(byTestId(container, 'saved-delete'));
  assert.equal(container.textContent?.includes('亲子科学馆半日'), false);

  await click(byTestId(container, 'details-close'));
  assert.equal(container.querySelector('[data-testid="saved-details-panel"]'), null);
});

test('settings tabs, preference toggles, and radius slider update visible state', async () => {
  const { container } = render(<SettingsView />);

  await click(byTestId(container, 'settings-tab-diet'));
  assert.ok(byTestId(container, 'settings-content').textContent?.includes('饮食限制'));

  const vegetarianToggle = byTestId<HTMLButtonElement>(container, 'preference-vegetarian');
  assert.equal(vegetarianToggle.getAttribute('aria-pressed'), 'false');
  await click(vegetarianToggle);
  assert.equal(vegetarianToggle.getAttribute('aria-pressed'), 'true');

  await click(byTestId(container, 'settings-tab-location'));
  const slider = byTestId<HTMLInputElement>(container, 'radius-slider');
  await inputText(slider, '8');
  assert.match(container.textContent ?? '', /8 公里/);
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
    input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
}
