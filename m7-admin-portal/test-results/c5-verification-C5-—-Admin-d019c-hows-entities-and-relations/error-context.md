# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: c5-verification.spec.ts >> C5 — Admin Layout & Sidebar >> knowledge graph page shows entities and relations
- Location: tests\e2e\c5-verification.spec.ts:173:7

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('Knowledge Graph')
Expected: visible
Timeout: 10000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 10000ms
  - waiting for getByText('Knowledge Graph')

```

```yaml
- heading "404" [level=1]
- heading "This page could not be found." [level=2]
- alert
```

# Test source

```ts
  75  |     await page.goto('/zh/admin');
  76  |     await expect(page.getByRole('button', { name: '仪表板' })).toBeVisible();
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
> 175 |     await expect(page.getByText('Knowledge Graph')).toBeVisible({ timeout: 10000 });
      |                                                     ^ Error: expect(locator).toBeVisible() failed
  176 | 
  177 |     // Entities tab: should show mock entities
  178 |     await expect(page.getByText('LNG Cargo Tank')).toBeVisible({ timeout: 8000 });
  179 |     await expect(page.getByText('DNV Pt.4 Ch.3 Sec.5')).toBeVisible();
  180 | 
  181 |     // All three tabs visible
  182 |     await expect(page.getByRole('tab', { name: 'Entities' })).toBeVisible();
  183 |     await expect(page.getByRole('tab', { name: 'Relations' })).toBeVisible();
  184 |     await expect(page.getByRole('tab', { name: 'Cross-Reference' })).toBeVisible();
  185 | 
  186 |     // Cross-Reference tab shows mock mappings
  187 |     await page.getByRole('tab', { name: 'Cross-Reference' }).click();
  188 |     await expect(page.getByText('LNG Cargo Tank Boundaries')).toBeVisible();
  189 |   });
  190 | 
  191 |   test('monitoring page shows module health and logs', async ({ page }) => {
  192 |     await page.goto('/en/admin/monitoring');
  193 |     await expect(page.getByText('System Monitoring')).toBeVisible({ timeout: 10000 });
  194 | 
  195 |     // Module health cards
  196 |     // Module health cards (inside Card components, not in log Badges)
  197 |     await expect(page.getByText('Healthy').first()).toBeVisible({ timeout: 8000 });
  198 |     await expect(page.getByText('Avg Retrieval Latency')).toBeVisible();
  199 |     await expect(page.getByText('Recent Logs')).toBeVisible();
  200 | 
  201 |     // Performance metrics
  202 |     await expect(page.getByText('Avg Retrieval Latency')).toBeVisible();
  203 | 
  204 |     // Recent logs
  205 |     await expect(page.getByText('Rate limit exceeded')).toBeVisible();
  206 |   });
  207 | });
  208 | 
```