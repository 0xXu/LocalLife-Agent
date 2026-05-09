import { expect, test } from '@playwright/test';

test('desktop demo completes plan, execution, and recovery', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('textbox').fill('今天下午是空的，想和老婆孩子出去玩几个小时，别离家太远。孩子 5 岁，老婆最近在减脂，帮我安排一下。');
  await page.getByRole('button', { name: '生成计划' }).click();

  await expect(page.getByText('已理解你的需求')).toBeVisible();
  await expect(page.getByText('Agent 执行轨迹')).toBeVisible();
  await expect(page.getByText('地图与路线').first()).toBeVisible();
  await expect(page.getByRole('heading', { level: 2, name: '主方案' })).toBeVisible();

  await page.getByRole('button', { name: '确认执行' }).click();
  await expect(page.getByText(/TKT-/).first()).toBeVisible();
  await expect(page.getByText(/RES-/).first()).toBeVisible();
  await expect(page.getByText(/CPN-/).first()).toBeVisible();
  await expect(page.getByText(/ORD-/).first()).toBeVisible();
  await expect(page.getByText(/MSG-/).first()).toBeVisible();
  await expect(page.getByText(/CAL-/).first()).toBeVisible();

  await page.getByRole('button', { name: '模拟餐厅无位' }).click();
  await expect(page.getByText('重新确认执行')).toBeVisible();
  await expect(page.getByText('原方案')).toBeVisible();
  await expect(page.getByText('新方案')).toBeVisible();
});
