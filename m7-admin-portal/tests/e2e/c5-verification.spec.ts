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
    await expect(page.getByText('Document Management')).toBeVisible({ timeout: 10000 });

    // Click LLM Config
    await page.getByRole('button', { name: 'LLM Config' }).click();
    await expect(page).toHaveURL(/\/en\/admin\/llm-config/);
    await expect(page.getByText('LLM Configuration')).toBeVisible();

    // Click back to Dashboard
    await page.getByRole('button', { name: 'Dashboard' }).click();
    await expect(page).toHaveURL(/\/en\/admin$/);
  });

  test('sidebar collapses to icon strip and expands back', async ({ page }) => {
    await page.goto('/en/admin');
    // Expanded: sidebar is 220px wide
    const sidebar = page.locator('aside.w-\\[220px\\]');
    await expect(sidebar).toBeVisible();

    // Collapse via PanelLeftClose button
    await page.locator('button').filter({ has: page.locator('svg.lucide-panel-left-close') }).first().click();

    // Collapsed: sidebar is now 56px wide (icon strip)
    const collapsedSidebar = page.locator('aside.w-\\[56px\\]');
    await expect(collapsedSidebar).toBeVisible({ timeout: 3000 });

    // Expand via PanelLeft button
    await page.locator('button').filter({ has: page.locator('svg.lucide-panel-left') }).first().click();
    await expect(sidebar).toBeVisible({ timeout: 3000 });
  });

  test('Chinese locale shows translated nav items', async ({ page }) => {
    await page.goto('/zh/admin');
    await expect(page.getByRole('button', { name: '仪表板' })).toBeVisible();
    await expect(page.getByRole('button', { name: '文档管理' })).toBeVisible();
    await expect(page.getByRole('button', { name: '知识图谱' })).toBeVisible();
  });

  test('settings page switches language from Chinese back to English', async ({ page }) => {
    await page.goto('/zh/admin/settings');
    await expect(page.getByText('界面语言')).toBeVisible();

    // Select English from dropdown
    await page.locator('select').selectOption('en');
    await expect(page).toHaveURL(/\/en\/admin\/settings/);
    await expect(page.getByText('Interface Language')).toBeVisible();
  });

  test('dashboard loads stats from mock API', async ({ page }) => {
    await page.goto('/en/admin');
    await expect(page.getByText('Dashboard')).toBeVisible();

    // Stats cards should show numbers (mock data: 47 docs, 12850 chunks, etc.)
    await expect(page.getByText('47')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('12,850')).toBeVisible();
    await expect(page.getByText('12', { exact: true })).toBeVisible();

    // Module health badges
    // Module health: underscores replaced with spaces in display
    await expect(page.getByText('M1 DOC PARSING')).toBeVisible();
    await expect(page.getByText('M5 QA ENGINE')).toBeVisible();
  });
});
