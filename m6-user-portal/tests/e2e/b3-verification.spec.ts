/**
 * Browser-level verification of B-III features.
 *
 * These tests run in a real Chromium browser and verify:
 * 1. Page loads with all expected UI elements
 * 2. Chat sends a message and citations appear
 * 3. Language switcher produces correct URLs
 *
 * Prerequisites:
 *   Mock Server must be running on http://127.0.0.1:8002
 *   Set: NEXT_PUBLIC_API_URL=http://127.0.0.1:8002
 */

import { test, expect } from '@playwright/test';

test.describe('B-III Verification', () => {
  test('page loads with sidebar, input, and empty state', async ({ page }) => {
    await page.goto('/en/chat');

    // Sidebar buttons exist
    await expect(page.getByText('New Chat')).toBeVisible();
    await expect(page.getByText('Search chats')).toBeVisible();
    await expect(page.getByText('Deep Research')).toBeVisible();

    // Sidebar bottom: Settings, Help, Log in
    await expect(page.getByText('Settings')).toBeVisible();
    await expect(page.getByText('Help')).toBeVisible();
    await expect(page.getByText('Log in')).toBeVisible();

    // Header shows app name
    await expect(page.getByText('MO Expert')).toBeVisible();

    // Input area
    await expect(page.getByPlaceholder(/Ask anything/)).toBeVisible();

    // Empty state shows suggestions
    const suggestionButtons = page.locator('button').filter({ hasText: /DNV|ABS|IMO|CCS/ });
    await expect(suggestionButtons.first()).toBeVisible();
  });

  test('clicking a suggestion sends a message with citations', async ({ page }) => {
    await page.goto('/en/chat');

    // Click the first suggestion question
    const suggestion = page.locator('button').filter({ hasText: /DNV requirements for LNG/ });
    await suggestion.click();

    // Wait for response to start streaming
    // The assistant message with "According to DNV" should appear
    await expect(page.getByText(/According to DNV/)).toBeVisible({ timeout: 15000 });

    // Citation badges should appear [1] and [2]
    // The citation badge contains the text like "[1] DNV Rules"
    const citationBadge = page.locator('[id^="msg-"]').last().getByText(/\[1\]/);
    await expect(citationBadge).toBeVisible({ timeout: 10000 });

    // Also verify [2] appears
    const citationBadge2 = page.locator('[id^="msg-"]').last().getByText(/\[2\]/);
    await expect(citationBadge2).toBeVisible({ timeout: 5000 });
  });

  test('language switcher produces correct URLs', async ({ page }) => {
    await page.goto('/en/chat');
    await expect(page).toHaveURL(/\/en\/chat/);

    // Open language dropdown — the trigger renders the current language text
    await page.locator('[data-slot="dropdown-menu-trigger"]').click();

    // Click Chinese
    await page.getByRole('menuitem', { name: '中文' }).click();

    // URL should be /zh/chat, NOT /zh/en/chat
    await expect(page).toHaveURL(/\/zh\/chat/);
    await expect(page).not.toHaveURL(/\/zh\/en/);

    // UI should now show Chinese text (language switcher shows "中文")
    await expect(page.locator('[data-slot="dropdown-menu-trigger"]')).toContainText('中文');

    // Switch to Korean
    await page.locator('[data-slot="dropdown-menu-trigger"]').click();
    await page.getByRole('menuitem', { name: '한국어' }).click();
    await expect(page).toHaveURL(/\/ko\/chat/);
    await expect(page).not.toHaveURL(/\/ko\/en/);

    // Switch to Japanese
    await page.locator('[data-slot="dropdown-menu-trigger"]').click();
    await page.getByRole('menuitem', { name: '日本語' }).click();
    await expect(page).toHaveURL(/\/ja\/chat/);

    // Switch to Norwegian
    await page.locator('[data-slot="dropdown-menu-trigger"]').click();
    await page.getByRole('menuitem', { name: 'Norsk' }).click();
    await expect(page).toHaveURL(/\/no\/chat/);

    // Switch back to English
    await page.locator('[data-slot="dropdown-menu-trigger"]').click();
    await page.getByRole('menuitem', { name: 'English' }).click();
    await expect(page).toHaveURL(/\/en\/chat/);
  });

  test('typing and sending a message produces a response', async ({ page }) => {
    await page.goto('/en/chat');

    // Type a question in the input
    const input = page.getByPlaceholder(/Ask anything/);
    await input.fill('What is IMO ballast water convention?');
    await input.press('Enter');

    // Response should appear (streaming) — look inside the prose div (Markdown content)
    const assistantMessage = page.locator('.prose').first();
    await expect(assistantMessage).toBeVisible({ timeout: 15000 });

    // Input should be cleared after sending
    await expect(input).toHaveValue('');
  });
});
