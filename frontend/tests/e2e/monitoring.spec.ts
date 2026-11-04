import { test, expect } from '@playwright/test';
import { signIn } from './support';

test('simulated monitoring completes, filters, shows details and stops explicitly', async ({ page }, info) => {
  await signIn(page);
  await page.goto('/fraud/monitoring');
  await page.getByLabel('Detection model').selectOption('');
  await page.getByLabel('Interval (seconds)').fill('1');
  await page.getByLabel('Maximum transactions').fill('2');
  await page.getByRole('button', { name: 'Start simulated stream', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Simulated stream · completed', exact: true })).toBeVisible();
  await expect(page.getByText('2 visible', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /· details$/ }).first().click();
  await expect(page.getByRole('heading', { name: 'Transaction details', exact: true })).toBeVisible();
  await expect(page.getByText(/Prediction: Not scored/)).toBeVisible();
  await expect(page.getByRole('link', { name: 'Explain saved prediction' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Close details' }).click();
  await page.getByLabel('Transaction search').fill('no-such-transaction');
  await expect(page.getByText('0 visible', { exact: true })).toBeVisible();
  await page.getByLabel('Transaction search').clear();
  await expect(page.getByText('2 visible', { exact: true })).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `test-results/monitoring-${info.project.name}.png`, fullPage: true });
  expect(await page.locator('body').evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
  await page.getByLabel('Maximum transactions').fill('100');
  await page.getByRole('button', { name: 'Start simulated stream', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Simulated stream · running', exact: true })).toBeVisible();
  await expect(page.locator('tbody tr').first()).toBeVisible();
  await page.getByRole('button', { name: 'Stop stream', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Simulated stream · stopped', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Stop stream', exact: true })).toBeDisabled();
});

