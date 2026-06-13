# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: b3-verification.spec.ts >> B-III Verification >> typing and sending a message produces a response
- Location: tests\e2e\b3-verification.spec.ts:110:7

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: locator('.prose').first()
Expected: visible
Timeout: 15000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 15000ms
  - waiting for locator('.prose').first()

```

```yaml
- button "New Chat"
- button "Search chats"
- button "Deep Research" [disabled]
- button "Projects" [disabled]:
  - img
  - text: Projects
- separator
- paragraph: Sign in to view your conversation history.
- separator
- button "Settings"
- button "Help"
- separator
- button "Log in"
- banner:
  - button "Collapse sidebar"
  - text: MO Expert
  - button "Share conversation"
- button "Copy"
- paragraph: What is IMO ballast water convention?
- button "Attach file"
- textbox "Ask anything about ship & offshore engineering..."
- button "Web search disabled"
- button "Send" [disabled]
- alert
```

# Test source

```ts
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
  119 |     const assistantMessage = page.locator('.prose').first();
> 120 |     await expect(assistantMessage).toBeVisible({ timeout: 15000 });
      |                                    ^ Error: expect(locator).toBeVisible() failed
  121 | 
  122 |     // Input should be cleared after sending
  123 |     await expect(input).toHaveValue('');
  124 |   });
  125 | 
  126 |   test('citation panel opens, switches, and does not blur background', async ({ page }) => {
  127 |     await page.goto('/en/chat');
  128 | 
  129 |     // Send a message that produces citations
  130 |     const suggestion = page.locator('button').filter({ hasText: /DNV requirements for LNG/ });
  131 |     await suggestion.click();
  132 | 
  133 |     // Wait for citation badges [1] and [2]
  134 |     const badge1 = page.locator('[id^="msg-"]').last().getByText(/\[1\]/);
  135 |     await expect(badge1).toBeVisible({ timeout: 15000 });
  136 | 
  137 |     // Click citation [1] — panel should open
  138 |     await badge1.click();
  139 |     const panel = page.locator('[data-slot="citation-panel"]');
  140 |     await expect(panel).toBeVisible({ timeout: 3000 });
  141 | 
  142 |     // Verify panel shows DNV citation details
  143 |     await expect(panel.getByText('DNV Rules for Classification of Ships')).toBeVisible();
  144 | 
  145 |     // Chat content must STILL be visible (not obscured by overlay)
  146 |     await expect(page.getByText(/According to DNV/)).toBeVisible();
  147 | 
  148 |     // No overlay element — panel is a column, not a modal
  149 |     const overlay = page.locator('[data-slot="sheet-overlay"]');
  150 |     await expect(overlay).toHaveCount(0);
  151 | 
  152 |     // Click citation [2] — panel should stay open, content should switch
  153 |     const badge2 = page.locator('[id^="msg-"]').last().getByText(/\[2\]/);
  154 |     await badge2.click();
  155 | 
  156 |     // Panel should still be visible
  157 |     await expect(panel).toBeVisible({ timeout: 2000 });
  158 |     // Panel should now show ABS citation details
  159 |     await expect(panel.getByText('ABS Rules for Building')).toBeVisible();
  160 | 
  161 |     // Close the panel by clicking the X button
  162 |     await panel.locator('button').first().click();
  163 |     await expect(panel).not.toBeVisible({ timeout: 2000 });
  164 |   });
  165 | 
  166 |   test('narrow viewport collapses sidebar to icon strip', async ({ page }) => {
  167 |     // Simulate a tablet-width viewport (800px — below 1024px threshold)
  168 |     await page.setViewportSize({ width: 800, height: 700 });
  169 |     await page.goto('/en/chat');
  170 | 
  171 |     // Sidebar text should NOT be visible (collapsed to icon strip)
  172 |     await expect(page.getByText('New Chat')).not.toBeVisible({ timeout: 3000 });
  173 | 
  174 |     // Icon strip should show a Plus icon (for new chat)
  175 |     const plusIcon = page.locator('svg.lucide-plus');
  176 |     await expect(plusIcon).toBeVisible({ timeout: 3000 });
  177 | 
  178 |     // Main content should still be visible
  179 |     await expect(page.getByText('MO Expert')).toBeVisible();
  180 |     await expect(page.getByPlaceholder(/Ask anything/)).toBeVisible();
  181 |   });
  182 | 
  183 |   test('login updates sidebar from guest to authenticated', async ({ page }) => {
  184 |     await page.goto('/en/login');
  185 |     await expect(page).toHaveURL(/\/en\/login/);
  186 | 
  187 |     // Login form should be visible
  188 |     await expect(page.getByRole('heading', { name: 'Sign In' })).toBeVisible();
  189 | 
  190 |     // Fill and submit
  191 |     await page.getByPlaceholder('Email').fill('engineer@shipyard.no');
  192 |     await page.getByPlaceholder('Password').fill('password123');
  193 |     await page.getByRole('button', { name: 'Sign In' }).click();
  194 | 
  195 |     // Should redirect to /chat
  196 |     await expect(page).toHaveURL(/\/en\/chat/, { timeout: 5000 });
  197 | 
  198 |     // Sidebar should now show logged-in state: avatar with username
  199 |     // Use exact match to avoid matching "engineering" in subtitle text
  200 |     await expect(page.getByText('engineer', { exact: true })).toBeVisible();
  201 |     // "Log in" button should be gone
  202 |     await expect(page.getByRole('button', { name: 'Log in' })).not.toBeVisible();
  203 | 
  204 |     // Logout via sidebar logout button
  205 |     const logoutBtn = page.getByTitle('Log out');
  206 |     await logoutBtn.click();
  207 |     await expect(page.getByRole('button', { name: 'Log in' })).toBeVisible({ timeout: 3000 });
  208 |   });
  209 | 
  210 |   test('knowledge base page shows documents from API', async ({ page }) => {
  211 |     await page.goto('/en/knowledge');
  212 |     await expect(page.getByText('Knowledge Base')).toBeVisible({ timeout: 5000 });
  213 | 
  214 |     // Should show mock documents (DNV, ABS, IMO)
  215 |     await expect(page.getByText('DNV-RU-SHIP-Pt4Ch3-2024.pdf')).toBeVisible({ timeout: 5000 });
  216 |     await expect(page.getByText('ABS-Rules-Pt5B-2024.pdf')).toBeVisible();
  217 |     await expect(page.getByText('IMO-BWMS-Code-2023.pdf')).toBeVisible();
  218 |   });
  219 | 
  220 |   test('jump navigation appears after multiple questions', async ({ page }) => {
```