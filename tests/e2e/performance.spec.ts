import assert from 'node:assert/strict';
import { expect, test } from '@playwright/test';

test('first complete plan appears within 10 seconds', async ({ page }) => {
  await page.goto('/');
  const start = Date.now();

  await page.getByRole('button', { name: '家庭半日' }).click();
  await expect(page.getByRole('heading', { level: 2, name: '主方案' })).toBeVisible({ timeout: 10_000 });

  assert.ok(Date.now() - start < 10_000);
});
