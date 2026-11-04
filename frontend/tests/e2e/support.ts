import { expect, type Page } from '@playwright/test';

export async function signIn(page: Page) {
  // Each case owns its account, so streams, drafts and datasets cannot leak
  // between browser tests or change another case's dashboard totals.
  const account = {
    email: `e2e-${crypto.randomUUID()}@example.com`,
    password: `Research-${crypto.randomUUID()}`,
  };
  await page.goto('/dashboard');
  await expect(page.getByRole('heading', { level: 1, name: 'Welcome back.' })).toBeVisible();
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await page.getByLabel('Display name').fill('E2E Researcher');
  await page.getByLabel('Email', { exact: true }).fill(account.email);
  await page.getByLabel('Password', { exact: true }).fill(account.password);
  await page.getByRole('button', { name: 'Create researcher account' }).click();
  await expect(page.getByRole('heading', { level: 1, name: /Intelligence starts/ })).toBeVisible({ timeout: 15000 });
  return account;
}
