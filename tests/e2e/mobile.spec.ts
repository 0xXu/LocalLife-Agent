import { expect, test } from '@playwright/test';
import { answerClarificationsUntilPlan } from './helpers';

test.use({ viewport: { width: 390, height: 844 } });

test('mobile layout completes the run flow from quick action', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '带娃出行' }).click();
  await answerClarificationsUntilPlan(page);

  const approvalLedger = page.getByText('Action Ledger');
  const completedState = page.getByText('执行完成');
  await expect(approvalLedger.or(completedState)).toBeVisible({ timeout: 30_000 });

  if (await approvalLedger.isVisible()) {
    await expect(page.getByText('执行账本')).toBeVisible();
    await expect(page.getByRole('button', { name: /批准执行/ })).toBeVisible();
  } else {
    await expect(page.getByText(/成功 \d+ \/ \d+ 项操作/)).toBeVisible();
  }

  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'AI助手' })).toBeVisible();
});
