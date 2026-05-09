import { expect, test } from '@playwright/test';

test.use({ viewport: { width: 390, height: 844 } });

test('mobile layout uses three-stage planner and collapsed map summary', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '家庭半日' }).click();

  await expect(page.getByText('已理解你的需求')).toBeVisible();
  await expect(page.getByTestId('planner-timeline')).toBeVisible();
  await expect(page.getByTestId('mobile-route-summary')).toBeVisible();
  await expect(page.getByTestId('bottom-execution-bar')).toBeVisible();
  await expect(page.getByTestId('desktop-map-panel')).toBeHidden();

  await expect(page.getByTestId('planner-timeline')).toHaveCSS('overflow-x', 'auto');
});
