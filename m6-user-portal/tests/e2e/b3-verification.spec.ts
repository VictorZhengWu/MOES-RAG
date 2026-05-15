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

  test('settings dialog: language switch and tabs work', async ({ page }) => {
    await page.goto('/en/chat');
    await expect(page).toHaveURL(/\/en\/chat/);

    // Open Settings via sidebar button
    await page.getByRole('button', { name: 'Settings' }).click();

    // Settings dialog should be visible
    const dialog = page.locator('.fixed.inset-0.z-50');
    await expect(dialog).toBeVisible({ timeout: 3000 });

    // Select Chinese from the language dropdown
    await dialog.locator('select').selectOption('zh');
    await expect(page).toHaveURL(/\/zh\/settings/);

    // Close settings (click backdrop), verify sidebar in Chinese
    await page.locator('.fixed.inset-0.z-50').click({ position: { x: 10, y: 10 } });
    await expect(page).toHaveURL(/\/zh\/chat/);
    await expect(page.getByText('新对话')).toBeVisible();
    await expect(page.getByText('设置')).toBeVisible();

    // Reopen settings, switch to Korean
    await page.getByRole('button', { name: '设置' }).click();
    await page.locator('select').selectOption('ko');
    await expect(page).toHaveURL(/\/ko\/settings/);

    // Close → back to /ko/chat
    await page.locator('.fixed.inset-0.z-50').click({ position: { x: 10, y: 10 } });
    await expect(page).toHaveURL(/\/ko\/chat/);
    await expect(page.getByText('새 대화')).toBeVisible();

    // Open settings, verify tabs are translated in Korean
    await page.getByRole('button', { name: '설정' }).click();
    // Tab buttons use translated labels (not hardcoded English)
    await expect(page.getByRole('button', { name: '일반' })).toBeVisible();
    await expect(page.getByRole('button', { name: '프로필' })).toBeVisible();
    await expect(page.getByRole('button', { name: '정보' })).toBeVisible();
    // Dialog title also shows active tab name (should NOT be "Settings")
    await expect(page.getByRole('heading', { name: '일반' })).toBeVisible();

    // Switch back to English
    await page.locator('select').selectOption('en');
    await expect(page).toHaveURL(/\/en\/settings/);
    await expect(page.getByRole('button', { name: 'General' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Profile' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'About' })).toBeVisible();
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

  test('citation panel opens, switches, and does not blur background', async ({ page }) => {
    await page.goto('/en/chat');

    // Send a message that produces citations
    const suggestion = page.locator('button').filter({ hasText: /DNV requirements for LNG/ });
    await suggestion.click();

    // Wait for citation badges [1] and [2]
    const badge1 = page.locator('[id^="msg-"]').last().getByText(/\[1\]/);
    await expect(badge1).toBeVisible({ timeout: 15000 });

    // Click citation [1] — panel should open
    await badge1.click();
    const panel = page.locator('[data-slot="citation-panel"]');
    await expect(panel).toBeVisible({ timeout: 3000 });

    // Verify panel shows DNV citation details
    await expect(panel.getByText('DNV Rules for Classification of Ships')).toBeVisible();

    // Chat content must STILL be visible (not obscured by overlay)
    await expect(page.getByText(/According to DNV/)).toBeVisible();

    // No overlay element — panel is a column, not a modal
    const overlay = page.locator('[data-slot="sheet-overlay"]');
    await expect(overlay).toHaveCount(0);

    // Click citation [2] — panel should stay open, content should switch
    const badge2 = page.locator('[id^="msg-"]').last().getByText(/\[2\]/);
    await badge2.click();

    // Panel should still be visible
    await expect(panel).toBeVisible({ timeout: 2000 });
    // Panel should now show ABS citation details
    await expect(panel.getByText('ABS Rules for Building')).toBeVisible();

    // Close the panel by clicking the X button
    await panel.locator('button').first().click();
    await expect(panel).not.toBeVisible({ timeout: 2000 });
  });

  test('narrow viewport hides sidebar but keeps content', async ({ page }) => {
    // Simulate a tablet-width viewport (800px — below 1024px threshold)
    await page.setViewportSize({ width: 800, height: 700 });
    await page.goto('/en/chat');

    // Sidebar should be hidden (auto-collapsed below 1024px)
    const sidebarText = page.getByText('New Chat');
    await expect(sidebarText).not.toBeVisible({ timeout: 3000 });

    // Main content should still be visible
    await expect(page.getByText('MO Expert')).toBeVisible();
    await expect(page.getByPlaceholder(/Ask anything/)).toBeVisible();
  });

  test('login updates sidebar from guest to authenticated', async ({ page }) => {
    await page.goto('/en/login');
    await expect(page).toHaveURL(/\/en\/login/);

    // Login form should be visible
    await expect(page.getByRole('heading', { name: 'Sign In' })).toBeVisible();

    // Fill and submit
    await page.getByPlaceholder('Email').fill('engineer@shipyard.no');
    await page.getByPlaceholder('Password').fill('password123');
    await page.getByRole('button', { name: 'Sign In' }).click();

    // Should redirect to /chat
    await expect(page).toHaveURL(/\/en\/chat/, { timeout: 5000 });

    // Sidebar should now show logged-in state: avatar with username
    // Use exact match to avoid matching "engineering" in subtitle text
    await expect(page.getByText('engineer', { exact: true })).toBeVisible();
    // "Log in" button should be gone
    await expect(page.getByRole('button', { name: 'Log in' })).not.toBeVisible();

    // Logout via sidebar logout button
    const logoutBtn = page.getByTitle('Log out');
    await logoutBtn.click();
    await expect(page.getByRole('button', { name: 'Log in' })).toBeVisible({ timeout: 3000 });
  });

  test('knowledge base page shows documents from API', async ({ page }) => {
    await page.goto('/en/knowledge');
    await expect(page.getByText('Knowledge Base')).toBeVisible({ timeout: 5000 });

    // Should show mock documents (DNV, ABS, IMO)
    await expect(page.getByText('DNV-RU-SHIP-Pt4Ch3-2024.pdf')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('ABS-Rules-Pt5B-2024.pdf')).toBeVisible();
    await expect(page.getByText('IMO-BWMS-Code-2023.pdf')).toBeVisible();
  });

  test('jump navigation appears after multiple questions', async ({ page }) => {
    await page.goto('/en/chat');

    // Send first question
    const input = page.getByPlaceholder(/Ask anything/);
    await input.fill('First question about DNV');
    await input.press('Enter');
    await expect(page.locator('.prose').first()).toBeVisible({ timeout: 15000 });

    // Send second question
    await input.fill('Second question about ABS');
    await input.press('Enter');
    await expect(page.locator('.prose').first()).toBeVisible({ timeout: 15000 });

    // Jump navigation strip should now be visible (2+ user messages)
    // It's a narrow strip on the right with MessageSquare icons
    const jumpStrip = page.locator('.w-12.shrink-0.border-l');
    await expect(jumpStrip).toBeVisible({ timeout: 3000 });
  });
});
