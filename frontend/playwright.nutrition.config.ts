import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  testMatch: 'nutrition.spec.ts',
  timeout: 90_000,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:5174',
    channel: 'msedge',
    viewport: { width: 1440, height: 1100 },
  },
  webServer: {
    command: 'npx vite --config tests/vite.audit.config.ts',
    url: 'http://127.0.0.1:5174',
    reuseExistingServer: false,
    timeout: 60_000,
  },
})
