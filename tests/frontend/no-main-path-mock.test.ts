import test from 'node:test';
import assert from 'node:assert/strict';
import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';

test('product source does not import legacy mock agent on the main path', async () => {
  const files = await sourceFiles(['app', 'components', 'features']);
  const offenders = files.filter((file) =>
    file.content.includes("from '@/src/agent.mjs'")
    || file.content.includes("from '../src/agent.mjs'")
    || file.content.includes('mockAgent')
  );
  assert.deepEqual(offenders.map((file) => file.path), []);
});

async function sourceFiles(roots: string[]) {
  const results: Array<{ path: string; content: string }> = [];
  for (const root of roots) {
    await collect(root, results);
  }
  return results;
}

async function collect(dir: string, results: Array<{ path: string; content: string }>) {
  const entries = await readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      await collect(path, results);
    } else if (/\.(js|jsx|ts|tsx|mjs)$/.test(entry.name)) {
      results.push({ path, content: await readFile(path, 'utf8') });
    }
  }
}
