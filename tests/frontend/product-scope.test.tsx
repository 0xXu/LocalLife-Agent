import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import {
  scenarioPrompts,
  savedPlans,
} from '../../features/planner/mockAgent';

test('scenario prompts expose all four detailed design entry points', () => {
  assert.deepEqual(Object.keys(scenarioPrompts).sort(), ['date', 'family', 'friends', 'rainy'].sort());
});

test('saved plan examples stay local-life and half-day scoped', async () => {
  const forbidden = ['海边短途', '山间休整', '10 月 14 - 15 日', '11 月 03 - 05 日', '山脉景区'];
  const serialized = JSON.stringify(savedPlans);
  const source = await readFile(new URL('../../features/planner/mockAgent.js', import.meta.url), 'utf8');

  for (const word of forbidden) {
    assert.equal(serialized.includes(word), false, `forbidden travel copy remains in data: ${word}`);
    assert.equal(source.includes(word), false, `forbidden travel copy remains in source: ${word}`);
  }
});
