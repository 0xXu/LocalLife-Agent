import assert from 'node:assert/strict';
import { expect, test } from '@playwright/test';

test('first clarification appears within 10 seconds', async ({ page }) => {
  await page.goto('/');
  const start = Date.now();

  await page.getByRole('button', { name: '带娃出行' }).click();
  await expect(page.getByText('我还需要确认一下')).toBeVisible({ timeout: 10_000 });

  assert.ok(Date.now() - start < 10_000);
});
