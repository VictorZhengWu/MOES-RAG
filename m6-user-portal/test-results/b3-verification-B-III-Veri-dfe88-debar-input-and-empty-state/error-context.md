# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: b3-verification.spec.ts >> B-III Verification >> page loads with sidebar, input, and empty state
- Location: tests\e2e\b3-verification.spec.ts:17:7

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: page.goto: net::ERR_ABORTED; maybe frame was detached?
Call log:
  - navigating to "http://localhost:3000/en/chat", waiting until "load"

```

# Test source

```ts
  1   | /**
  2   |  * Browser-level verification of B-III features.
  3   |  *
  4   |  * These tests run in a real Chromium browser and verify:
  5   |  * 1. Page loads with all expected UI elements
  6   |  * 2. Chat sends a message and citations appear
  7   |  * 3. Language switcher produces correct URLs
  8   |  *
  9   |  * Prerequisites:
  10  |  *   Mock Server must be running on http://127.0.0.1:8002
  11  |  *   Set: NEXT_PUBLIC_API_URL=http://127.0.0.1:8002
  12  |  */
  13  | 
  14  | import { test, expect } from '@playwright/test';
  15  | 
  16  | test.describe('B-III Verification', () => {
  17  |   test('page loads with sidebar, input, and empty state', async ({ page }) => {
> 18  |     await page.goto('/en/chat');
      |                ^ Error: page.goto: net::ERR_ABORTED; maybe frame was detached?
  19  | 
  20  |     // Sidebar buttons exist
  21  |     await expect(page.getByText('New Chat')).toBeVisible();
  22  |     await expect(page.getByText('Search chats')).toBeVisible();
  23  |     await expect(page.getByText('Deep Research')).toBeVisible();
  24  | 
  25  |     // Sidebar bottom: Settings, Help, Log in
  26  |     await expect(page.getByText('Settings')).toBeVisible();
  27  |     await expect(page.getByText('Help')).toBeVisible();
  28  |     await expect(page.getByText('Log in')).toBeVisible();
  29  | 
  30  |     // Header shows app name
  31  |     await expect(page.getByText('MO Expert')).toBeVisible();
  32  | 
  33  |     // Input area
  34  |     await expect(page.getByPlaceholder(/Ask anything/)).toBeVisible();
  35  | 
  36  |     // Empty state shows suggestions
  37  |     const suggestionButtons = page.locator('button').filter({ hasText: /DNV|ABS|IMO|CCS/ });
  38  |     await expect(suggestionButtons.first()).toBeVisible();
  39  |   });
  40  | 
  41  |   test('clicking a suggestion sends a message with citations', async ({ page }) => {
  42  |     await page.goto('/en/chat');
  43  | 
  44  |     // Click the first suggestion question
  45  |     const suggestion = page.locator('button').filter({ hasText: /DNV requirements for LNG/ });
  46  |     await suggestion.click();
  47  | 
  48  |     // Wait for response to start streaming
  49  |     // The assistant message with "According to DNV" should appear
  50  |     await expect(page.getByText(/According to DNV/)).toBeVisible({ timeout: 15000 });
  51  | 
  52  |     // Citation badges should appear [1] and [2]
  53  |     // The citation badge contains the text like "[1] DNV Rules"
  54  |     const citationBadge = page.locator('[id^="msg-"]').last().getByText(/\[1\]/);
  55  |     await expect(citationBadge).toBeVisible({ timeout: 10000 });
  56  | 
  57  |     // Also verify [2] appears
  58  |     const citationBadge2 = page.locator('[id^="msg-"]').last().getByText(/\[2\]/);
  59  |     await expect(citationBadge2).toBeVisible({ timeout: 5000 });
  60  |   });
  61  | 
  62  |   test('settings dialog: language switch and tabs work', async ({ page }) => {
  63  |     await page.goto('/en/chat');
  64  |     await expect(page).toHaveURL(/\/en\/chat/);
  65  | 
  66  |     // Open Settings via sidebar button
  67  |     await page.getByRole('button', { name: 'Settings' }).click();
  68  | 
  69  |     // Settings dialog should be visible
  70  |     const dialog = page.locator('.fixed.inset-0.z-50');
  71  |     await expect(dialog).toBeVisible({ timeout: 3000 });
  72  | 
  73  |     // Select Chinese from the language dropdown
  74  |     await dialog.locator('select').selectOption('zh');
  75  |     await expect(page).toHaveURL(/\/zh\/settings/);
  76  | 
  77  |     // Close settings (click backdrop), verify sidebar in Chinese
  78  |     await page.locator('.fixed.inset-0.z-50').click({ position: { x: 10, y: 10 } });
  79  |     await expect(page).toHaveURL(/\/zh\/chat/);
  80  |     await expect(page.getByText('新对话')).toBeVisible();
  81  |     await expect(page.getByText('设置')).toBeVisible();
  82  | 
  83  |     // Reopen settings, switch to Korean
  84  |     await page.getByRole('button', { name: '设置' }).click();
  85  |     await page.locator('select').selectOption('ko');
  86  |     await expect(page).toHaveURL(/\/ko\/settings/);
  87  | 
  88  |     // Close → back to /ko/chat
  89  |     await page.locator('.fixed.inset-0.z-50').click({ position: { x: 10, y: 10 } });
  90  |     await expect(page).toHaveURL(/\/ko\/chat/);
  91  |     await expect(page.getByText('새 대화')).toBeVisible();
  92  | 
  93  |     // Open settings, verify tabs are translated in Korean
  94  |     await page.getByRole('button', { name: '설정' }).click();
  95  |     // Tab buttons use translated labels (not hardcoded English)
  96  |     await expect(page.getByRole('button', { name: '일반' })).toBeVisible();
  97  |     await expect(page.getByRole('button', { name: '프로필' })).toBeVisible();
  98  |     await expect(page.getByRole('button', { name: '정보' })).toBeVisible();
  99  |     // Dialog title also shows active tab name (should NOT be "Settings")
  100 |     await expect(page.getByRole('heading', { name: '일반' })).toBeVisible();
  101 | 
  102 |     // Switch back to English
  103 |     await page.locator('select').selectOption('en');
  104 |     await expect(page).toHaveURL(/\/en\/settings/);
  105 |     await expect(page.getByRole('button', { name: 'General' })).toBeVisible();
  106 |     await expect(page.getByRole('button', { name: 'Profile' })).toBeVisible();
  107 |     await expect(page.getByRole('button', { name: 'About' })).toBeVisible();
  108 |   });
  109 | 
  110 |   test('typing and sending a message produces a response', async ({ page }) => {
  111 |     await page.goto('/en/chat');
  112 | 
  113 |     // Type a question in the input
  114 |     const input = page.getByPlaceholder(/Ask anything/);
  115 |     await input.fill('What is IMO ballast water convention?');
  116 |     await input.press('Enter');
  117 | 
  118 |     // Response should appear (streaming) — look inside the prose div (Markdown content)
```