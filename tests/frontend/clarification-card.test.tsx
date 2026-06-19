import test from 'node:test';
import assert from 'node:assert/strict';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { JSDOM } from 'jsdom';

import { ClarificationCard } from '../../components/clarification/ClarificationCard';
import { ChatView } from '../../components/chat/ChatView';

type Submission = { questionId: string; answer: unknown };

const partySizeQuestion = {
  id: 'party_size',
  label: '这次一共有几位？',
  description: '人数会影响餐厅容量、预算和路线时间。',
  kind: 'number' as const,
  required: true,
  options: [
    { label: '1 位', value: 1 },
    { label: '2 位', value: 2 },
    { label: '3 位', value: 3 },
  ],
  allow_custom: true,
  validation: { min: 1, max: 20 },
};

test('clarification card submits selected numeric option', async () => {
  const submissions: Submission[] = [];
  const { container } = render(
    <ClarificationCard
      question={partySizeQuestion}
      onSubmit={(questionId, answer) => submissions.push({ questionId, answer })}
    />,
  );

  await click(byTestId(container, 'clarification-option-2'));
  await click(byTestId(container, 'clarification-submit'));

  assert.deepEqual(submissions, [{ questionId: 'party_size', answer: 2 }]);
});

test('clarification card submits a custom numeric answer', async () => {
  const submissions: Submission[] = [];
  const { container } = render(
    <ClarificationCard
      question={partySizeQuestion}
      onSubmit={(questionId, answer) => submissions.push({ questionId, answer })}
    />,
  );

  await inputText(byTestId<HTMLInputElement>(container, 'clarification-custom-input'), '5');
  await click(byTestId(container, 'clarification-submit'));

  assert.deepEqual(submissions, [{ questionId: 'party_size', answer: 5 }]);
});

test('chat view renders clarification as an assistant conversation turn', () => {
  const { container } = render(
    <ChatView
      goal="今天下午想出去玩"
      onSubmitGoal={() => {}}
      isPlanning={false}
      error={null}
      clarificationQuestion={partySizeQuestion}
      onAnswerClarification={() => {}}
    />,
  );

  assert.match(container.textContent ?? '', /今天下午想出去玩/);
  assert.match(container.textContent ?? '', /这次一共有几位/);
  assert.equal(container.querySelectorAll('.chat-bubble--ai .clarification-card').length, 1);
});

test('clarification card uses compact in-chat copy', () => {
  const { container } = render(
    <ClarificationCard
      question={partySizeQuestion}
      onSubmit={() => {}}
    />,
  );

  assert.doesNotMatch(container.textContent ?? '', /需要补充一个信息/);
  assert.match(container.textContent ?? '', /我还需要确认一下/);
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
  globalThis.MouseEvent = dom.window.MouseEvent;
  (globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

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
    const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), 'value')?.set;
    setter?.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
}
