import assert from 'node:assert/strict';
import { expect, test } from '@playwright/test';

test('first complete plan appears within 10 seconds', async ({ page }) => {
  await page.goto('/');
  const start = Date.now();

  await page.getByRole('button', { name: '带娃出行' }).click();
  await expect(page.getByText('需要补充一个信息')).toBeVisible({ timeout: 10_000 });
  await page.getByRole('button', { name: /今天下午 2 点/ }).click();
  await page.getByRole('button', { name: /继续生成/ }).click();
  await expect(page.getByText('Action Ledger').or(page.getByText('执行完成'))).toBeVisible({ timeout: 10_000 });

  assert.ok(Date.now() - start < 10_000);
});
