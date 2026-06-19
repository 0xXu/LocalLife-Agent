import { expect, type Page } from '@playwright/test';

export async function answerClarificationsUntilPlan(page: Page) {
  const answers = [
    /今天下午 2 点/,
    /家附近/,
    /2 位/,
    /散步逛逛/,
  ];

  for (const answer of answers) {
    const approvalLedger = page.getByText('Action Ledger');
    const completedState = page.getByText('执行完成');
    if (await approvalLedger.or(completedState).isVisible().catch(() => false)) return;

    await expect(page.getByText('我还需要确认一下')).toBeVisible({ timeout: 30_000 });
    await page.getByRole('button', { name: answer }).click();
    await page.getByRole('button', { name: /继续生成/ }).click();
  }
}
