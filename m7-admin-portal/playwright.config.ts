import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30000,
  retries: 0,
  use: { baseURL: 'http://localhost:3000', headless: true },
  webServer: { command: 'npm run dev', port: 3000, reuseExistingServer: true, timeout: 30000, env: { NEXT_PUBLIC_API_URL: 'http://127.0.0.1:8002' } },
});
