import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  testMatch: 'docker-staff-fua.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 180_000,
  reporter: [['list']],
  outputDir: process.env.DOCKER_E2E_EVIDENCE || '../output/docker-staff-fua/browser',
  use: {
    baseURL: process.env.DOCKER_E2E_URL,
    viewport: { width: 1440, height: 1100 },
    screenshot: 'only-on-failure',
    trace: 'off',
    video: 'off',
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : {},
  },
})
