# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: c5-verification.spec.ts >> C5 — Admin Layout & Sidebar >> Chinese locale shows translated nav items
- Location: tests\e2e\c5-verification.spec.ts:74:7

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('button', { name: '仪表板' })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for getByRole('button', { name: '仪表板' })

```

```yaml
- heading "404" [level=1]
- heading "This page could not be found." [level=2]
- alert
```

# Test source

```ts
  1   | /**
  2   |  * Browser-level verification of M7 Phase C-5 (AdminLayout + AdminSidebar).
  3   |  *
  4   |  * Prerequisites: none (Playwright auto-starts the dev server).
  5   |  */
  6   | import { test, expect } from '@playwright/test';
  7   | 
  8   | test.describe('C5 — Admin Layout & Sidebar', () => {
  9   |   // Set admin auth token before each test (bypasses Auth Guard)
  10  |   test.beforeEach(async ({ page }) => {
  11  |     await page.goto('/');
  12  |     await page.evaluate(() => {
  13  |       localStorage.setItem('m7-admin-auth', 'true');
  14  |       localStorage.setItem('m7-admin-user', 'admin');
  15  |     });
  16  |   });
  17  | 
  18  |   test('redirects / to /en/admin', async ({ page }) => {
  19  |     await page.goto('/');
  20  |     await expect(page).toHaveURL(/\/en\/admin/);
  21  |   });
  22  | 
  23  |   test('admin sidebar shows all 6 nav items', async ({ page }) => {
  24  |     await page.goto('/en/admin');
  25  | 
  26  |     // Sidebar brand
  27  |     await expect(page.getByText('MO Admin')).toBeVisible();
  28  | 
  29  |     // All 6 nav items visible (use button role to distinguish from page titles)
  30  |     await expect(page.getByRole('button', { name: 'Dashboard' })).toBeVisible();
  31  |     await expect(page.getByRole('button', { name: 'Documents' })).toBeVisible();
  32  |     await expect(page.getByRole('button', { name: 'Knowledge Graph' })).toBeVisible();
  33  |     await expect(page.getByRole('button', { name: 'LLM Config' })).toBeVisible();
  34  |     await expect(page.getByRole('button', { name: 'Users' })).toBeVisible();
  35  |     await expect(page.getByRole('button', { name: 'Monitoring' })).toBeVisible();
  36  |   });
  37  | 
  38  |   test('sidebar navigation switches pages', async ({ page }) => {
  39  |     await page.goto('/en/admin');
  40  | 
  41  |     // Click Documents
  42  |     await page.getByRole('button', { name: 'Documents' }).click();
  43  |     await expect(page).toHaveURL(/\/en\/admin\/documents/);
  44  |     await expect(page.getByText('Document Management')).toBeVisible({ timeout: 10000 });
  45  | 
  46  |     // Click LLM Config
  47  |     await page.getByRole('button', { name: 'LLM Config' }).click();
  48  |     await expect(page).toHaveURL(/\/en\/admin\/llm-config/);
  49  |     await expect(page.getByText('LLM Configuration')).toBeVisible();
  50  | 
  51  |     // Click back to Dashboard
  52  |     await page.getByRole('button', { name: 'Dashboard' }).click();
  53  |     await expect(page).toHaveURL(/\/en\/admin$/);
  54  |   });
  55  | 
  56  |   test('sidebar collapses to icon strip and expands back', async ({ page }) => {
  57  |     await page.goto('/en/admin');
  58  |     // Expanded: sidebar is 220px wide
  59  |     const sidebar = page.locator('aside.w-\\[220px\\]');
  60  |     await expect(sidebar).toBeVisible();
  61  | 
  62  |     // Collapse via PanelLeftClose button
  63  |     await page.locator('button').filter({ has: page.locator('svg.lucide-panel-left-close') }).first().click();
  64  | 
  65  |     // Collapsed: sidebar is now 56px wide (icon strip)
  66  |     const collapsedSidebar = page.locator('aside.w-\\[56px\\]');
  67  |     await expect(collapsedSidebar).toBeVisible({ timeout: 3000 });
  68  | 
  69  |     // Expand via PanelLeft button
  70  |     await page.locator('button').filter({ has: page.locator('svg.lucide-panel-left') }).first().click();
  71  |     await expect(sidebar).toBeVisible({ timeout: 3000 });
  72  |   });
  73  | 
  74  |   test('Chinese locale shows translated nav items', async ({ page }) => {
  75  |     await page.goto('/zh/admin');
> 76  |     await expect(page.getByRole('button', { name: '仪表板' })).toBeVisible();
      |                                                             ^ Error: expect(locator).toBeVisible() failed
  77  |     await expect(page.getByRole('button', { name: '文档管理' })).toBeVisible();
  78  |     await expect(page.getByRole('button', { name: '知识图谱' })).toBeVisible();
  79  |   });
  80  | 
  81  |   test('settings page switches language from Chinese back to English', async ({ page }) => {
  82  |     await page.goto('/zh/admin/settings');
  83  |     await expect(page.getByText('界面语言')).toBeVisible();
  84  | 
  85  |     // Select English from dropdown
  86  |     await page.locator('select').selectOption('en');
  87  |     await expect(page).toHaveURL(/\/en\/admin\/settings/);
  88  |     await expect(page.getByText('Interface Language')).toBeVisible();
  89  |   });
  90  | 
  91  |   test('dashboard loads stats from mock API', async ({ page }) => {
  92  |     await page.goto('/en/admin');
  93  |     await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  94  | 
  95  |     // Stats cards should show numbers (mock data: 47 docs, 12850 chunks, etc.)
  96  |     await expect(page.getByText('47')).toBeVisible({ timeout: 5000 });
  97  |     await expect(page.getByText('12,850')).toBeVisible();
  98  |     await expect(page.getByText('12', { exact: true })).toBeVisible();
  99  | 
  100 |     // Module health badges
  101 |     // Module health: underscores replaced with spaces in display
  102 |     await expect(page.getByText('M1 DOC PARSING')).toBeVisible();
  103 |     await expect(page.getByText('M5 QA ENGINE')).toBeVisible();
  104 |   });
  105 | 
  106 |   test('documents page shows upload area and mock document list', async ({ page }) => {
  107 |     await page.goto('/en/admin/documents');
  108 |     await expect(page.getByText('Document Management')).toBeVisible({ timeout: 10000 });
  109 | 
  110 |     // Upload area with format hint visible
  111 |     await expect(page.getByText(/Drop files here/)).toBeVisible();
  112 |     await expect(page.getByText(/\[Society\]\[Category\]\[Section\]\[Name\]\[YYYYMM\]/)).toBeVisible();
  113 | 
  114 |     // Mock documents from API
  115 |     await expect(page.getByText('DNV-RU-SHIP-Pt4Ch3-2024.pdf')).toBeVisible({ timeout: 8000 });
  116 |     await expect(page.getByText('IMO-BWMS-Code-2023.pdf')).toBeVisible();
  117 |   });
  118 | 
  119 |   test('filename parser correctly parses structured filenames', async () => {
  120 |     // Test the filename parsing regex directly (same as filename-parser.ts)
  121 |     const RE = /\[([A-Z]+)\]\[([A-Z\-0-9]+)\]\[([^\]]+)\]\[([^\]]+)\]\[(\d{6})\]/;
  122 | 
  123 |     // Valid RU-SHIP filename
  124 |     const raw1 = '[DNV][RU-SHIP][Pt.1-Ch.1][General regulations][202507].pdf';
  125 |     const dot1 = raw1.lastIndexOf('.');
  126 |     const m1 = raw1.substring(0, dot1).match(RE);
  127 |     expect(m1).toBeTruthy();
  128 |     if (m1) {
  129 |       expect(m1[1]).toBe('DNV');
  130 |       expect(m1[2]).toBe('RU-SHIP');
  131 |       expect(m1[3]).toBe('Pt.1-Ch.1');
  132 |       expect(m1[4]).toBe('General regulations');
  133 |       expect(m1[5]).toBe('202507');
  134 |     }
  135 | 
  136 |     // Valid OS filename
  137 |     const m2 = '[DNV][OS][D201][Electrical installations][202507].pdf'.match(RE);
  138 |     expect(m2).toBeTruthy();
  139 |     if (m2) { expect(m2[2]).toBe('OS'); expect(m2[3]).toBe('D201'); }
  140 | 
  141 |     // Invalid filename — no match
  142 |     const m3 = 'random-document.pdf'.match(RE);
  143 |     expect(m3).toBeNull();
  144 |   });
  145 | 
  146 |   test('llm config page shows 7 purpose boxes', async ({ page }) => {
  147 |     await page.goto('/en/admin/llm-config');
  148 |     await expect(page.getByText('LLM Configuration')).toBeVisible({ timeout: 10000 });
  149 | 
  150 |     // 7 purpose boxes should be visible
  151 |     await expect(page.getByText('Chat Model')).toBeVisible();
  152 |     await expect(page.getByText('Reasoning Model')).toBeVisible();
  153 |     await expect(page.getByText('Embedding Model')).toBeVisible();
  154 |     await expect(page.getByText('Reranking Model')).toBeVisible();
  155 |     await expect(page.getByText('OCR Model')).toBeVisible();
  156 |     await expect(page.getByText('Vision / Multimodal Model')).toBeVisible();
  157 |     await expect(page.getByText('Document Parsing Engine')).toBeVisible();
  158 | 
  159 |     // Each box has a Test Connection button
  160 |     const testButtons = page.getByText('Test Connection');
  161 |     await expect(testButtons).toHaveCount(7);
  162 |   });
  163 | 
  164 |   test('users page shows mock users from API', async ({ page }) => {
  165 |     await page.goto('/en/admin/users');
  166 |     await expect(page.getByText('User Management')).toBeVisible({ timeout: 10000 });
  167 |     // "admin" appears in sidebar brand "MO Admin" too — use exact match
  168 |     // Mock users: admin (admin@shipyard.no) + editor_li (li.wang@shipyard.cn)
  169 |     await expect(page.getByText('admin@shipyard.no')).toBeVisible({ timeout: 8000 });
  170 |     await expect(page.getByText('li.wang@shipyard.cn')).toBeVisible();
  171 |   });
  172 | 
  173 |   test('knowledge graph page shows entities and relations', async ({ page }) => {
  174 |     await page.goto('/en/admin/knowledge-graph');
  175 |     await expect(page.getByText('Knowledge Graph')).toBeVisible({ timeout: 10000 });
  176 | 
```