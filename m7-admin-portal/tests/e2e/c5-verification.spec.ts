/**
 * Browser-level verification of M7 Phase C-5 (AdminLayout + AdminSidebar).
 *
 * Prerequisites: none (Playwright auto-starts the dev server).
 */
import { test, expect } from '@playwright/test';

test.describe('C5 — Admin Layout & Sidebar', () => {
  test('redirects / to /en/admin', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/en\/admin/);
  });

  test('admin sidebar shows all 6 nav items', async ({ page }) => {
    await page.goto('/en/admin');

    // Sidebar brand
    await expect(page.getByText('MO Admin')).toBeVisible();

    // All 6 nav items visible (use button role to distinguish from page titles)
    await expect(page.getByRole('button', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Documents' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Knowledge Graph' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'LLM Config' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Users' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Monitoring' })).toBeVisible();
  });

  test('sidebar navigation switches pages', async ({ page }) => {
    await page.goto('/en/admin');

    // Click Documents
    await page.getByRole('button', { name: 'Documents' }).click();
    await expect(page).toHaveURL(/\/en\/admin\/documents/);
    await expect(page.getByText('Document Management')).toBeVisible();

    // Click LLM Config
    await page.getByRole('button', { name: 'LLM Config' }).click();
    await expect(page).toHaveURL(/\/en\/admin\/llm-config/);
    await expect(page.getByText('LLM Configuration')).toBeVisible();

    // Click back to Dashboard
    await page.getByRole('button', { name: 'Dashboard' }).click();
    await expect(page).toHaveURL(/\/en\/admin$/);
  });

  test('language switcher changes locale and URL', async ({ page }) => {
    await page.goto('/en/admin');

    // Switch to Chinese
    await page.locator('select').selectOption('zh');
    await expect(page).toHaveURL(/\/zh\/admin/);
    // Sidebar should re-render in Chinese locale
    await expect(page.getByText('MO Admin')).toBeVisible();
  });
});
