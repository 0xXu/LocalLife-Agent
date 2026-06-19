import { expect, test } from '@playwright/test';

test('desktop demo completes run approval and execution', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('textbox', { name: '输入出行需求' }).fill('今天下午是空的，想和老婆孩子出去玩几个小时，别离家太远。孩子 5 岁，老婆最近在减脂，帮我安排一下。');
  await page.getByRole('button', { name: '发送' }).click();

  const approvalLedger = page.getByText('Action Ledger');
  const completedState = page.getByText('执行完成');
  await expect(approvalLedger.or(completedState)).toBeVisible({ timeout: 30_000 });

  if (await approvalLedger.isVisible()) {
    await expect(page.getByText('执行账本')).toBeVisible();
    await expect(page.getByText('待执行').first()).toBeVisible();
    await expect(page.getByRole('button', { name: /批准执行/ })).toBeEnabled();
    await page.getByRole('button', { name: /批准执行/ }).click();
    await expect(completedState).toBeVisible();
  }

  await expect(page.getByText(/成功 \d+ \/ \d+ 项操作/)).toBeVisible();
});
