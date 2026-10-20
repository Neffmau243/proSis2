import { defineConfig } from '@playwright/test'

/**
 * E2E de navegador solo para lo que Vitest no puede cubrir: la calibración en
 * milímetros, el `localStorage` y la salida de impresión que arma el diálogo FUA.
 * Por defecto sirve el arnés sintético de Vite. La prueba de Referencia usa
 * una API y una base desechables, iniciadas por run_referral_e2e.py.
 */
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
const referralUrl = process.env.REFERRAL_E2E_URL

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL: referralUrl || 'http://127.0.0.1:5178',
    trace: 'off',
    ...(executablePath ? { launchOptions: { executablePath } } : {}),
  },
  webServer: referralUrl
    ? undefined
    : {
        command: 'npx vite --host 127.0.0.1 --port 5178 --strictPort',
        url: 'http://127.0.0.1:5178/tests/fua-print-harness.html',
        reuseExistingServer: true,
        timeout: 120_000,
      },
})
