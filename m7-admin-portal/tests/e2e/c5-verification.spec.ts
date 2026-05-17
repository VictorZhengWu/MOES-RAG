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
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();

    // Stats cards should show numbers (mock data: 47 docs, 12850 chunks, etc.)
    await expect(page.getByText('47')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('12,850')).toBeVisible();
    await expect(page.getByText('12', { exact: true })).toBeVisible();

    // Module health badges
    // Module health: underscores replaced with spaces in display
    await expect(page.getByText('M1 DOC PARSING')).toBeVisible();
    await expect(page.getByText('M5 QA ENGINE')).toBeVisible();
  });

  test('documents page shows upload area and mock document list', async ({ page }) => {
    await page.goto('/en/admin/documents');
    await expect(page.getByText('Document Management')).toBeVisible({ timeout: 10000 });

    // Upload area with format hint visible
    await expect(page.getByText(/Drop files here/)).toBeVisible();
    await expect(page.getByText(/\[Society\]\[Category\]\[Section\]\[Name\]\[YYYYMM\]/)).toBeVisible();

    // Mock documents from API
    await expect(page.getByText('DNV-RU-SHIP-Pt4Ch3-2024.pdf')).toBeVisible({ timeout: 8000 });
    await expect(page.getByText('IMO-BWMS-Code-2023.pdf')).toBeVisible();
  });

  test('filename parser correctly parses structured filenames', async () => {
    // Test the filename parsing regex directly (same as filename-parser.ts)
    const RE = /\[([A-Z]+)\]\[([A-Z\-0-9]+)\]\[([^\]]+)\]\[([^\]]+)\]\[(\d{6})\]/;

    // Valid RU-SHIP filename
    const raw1 = '[DNV][RU-SHIP][Pt.1-Ch.1][General regulations][202507].pdf';
    const dot1 = raw1.lastIndexOf('.');
    const m1 = raw1.substring(0, dot1).match(RE);
    expect(m1).toBeTruthy();
    if (m1) {
      expect(m1[1]).toBe('DNV');
      expect(m1[2]).toBe('RU-SHIP');
      expect(m1[3]).toBe('Pt.1-Ch.1');
      expect(m1[4]).toBe('General regulations');
      expect(m1[5]).toBe('202507');
    }

    // Valid OS filename
    const m2 = '[DNV][OS][D201][Electrical installations][202507].pdf'.match(RE);
    expect(m2).toBeTruthy();
    if (m2) { expect(m2[2]).toBe('OS'); expect(m2[3]).toBe('D201'); }

    // Invalid filename — no match
    const m3 = 'random-document.pdf'.match(RE);
    expect(m3).toBeNull();
  });

  test('llm config page shows 7 purpose boxes', async ({ page }) => {
    await page.goto('/en/admin/llm-config');
    await expect(page.getByText('LLM Configuration')).toBeVisible({ timeout: 10000 });

    // 7 purpose boxes should be visible
    await expect(page.getByText('Chat Model')).toBeVisible();
    await expect(page.getByText('Reasoning Model')).toBeVisible();
    await expect(page.getByText('Embedding Model')).toBeVisible();
    await expect(page.getByText('Reranking Model')).toBeVisible();
    await expect(page.getByText('OCR Model')).toBeVisible();
    await expect(page.getByText('Vision / Multimodal Model')).toBeVisible();
    await expect(page.getByText('Document Parsing Engine')).toBeVisible();

    // Each box has a Test Connection button
    const testButtons = page.getByText('Test Connection');
    await expect(testButtons).toHaveCount(7);
  });

  test('users page shows mock users from API', async ({ page }) => {
    await page.goto('/en/admin/users');
    await expect(page.getByText('User Management')).toBeVisible({ timeout: 10000 });
    // "admin" appears in sidebar brand "MO Admin" too — use exact match
    // Mock users: admin (admin@shipyard.no) + editor_li (li.wang@shipyard.cn)
    await expect(page.getByText('admin@shipyard.no')).toBeVisible({ timeout: 8000 });
    await expect(page.getByText('li.wang@shipyard.cn')).toBeVisible();
  });

  test('knowledge graph page shows entities and relations', async ({ page }) => {
    await page.goto('/en/admin/knowledge-graph');
    await expect(page.getByText('Knowledge Graph')).toBeVisible({ timeout: 10000 });

    // Entities tab: should show mock entities
    await expect(page.getByText('LNG Cargo Tank')).toBeVisible({ timeout: 8000 });
    await expect(page.getByText('DNV Pt.4 Ch.3 Sec.5')).toBeVisible();

    // All three tabs visible
    await expect(page.getByRole('tab', { name: 'Entities' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Relations' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Cross-Reference' })).toBeVisible();

    // Cross-Reference tab shows mock mappings
    await page.getByRole('tab', { name: 'Cross-Reference' }).click();
    await expect(page.getByText('LNG Cargo Tank Boundaries')).toBeVisible();
  });

  test('monitoring page shows module health and logs', async ({ page }) => {
    await page.goto('/en/admin/monitoring');
    await expect(page.getByText('System Monitoring')).toBeVisible({ timeout: 10000 });

    // Module health cards
    // Module health cards (inside Card components, not in log Badges)
    await expect(page.getByText('Healthy').first()).toBeVisible({ timeout: 8000 });
    await expect(page.getByText('Avg Retrieval Latency')).toBeVisible();
    await expect(page.getByText('Recent Logs')).toBeVisible();

    // Performance metrics
    await expect(page.getByText('Avg Retrieval Latency')).toBeVisible();

    // Recent logs
    await expect(page.getByText('Rate limit exceeded')).toBeVisible();
  });
});
