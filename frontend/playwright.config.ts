import { defineConfig } from '@playwright/test'

/**
 * E2E de navegador solo para lo que Vitest no puede cubrir: la calibración en
 * milímetros, el `localStorage` y la salida de impresión que arma el diálogo FUA.
 * Sirve el arnés sintético de Vite: no toca el backend ni datos reales.
 */
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:5178',
    trace: 'off',
    ...(executablePath ? { launchOptions: { executablePath } } : {}),
  },
  webServer: {
    command: 'npx vite --host 127.0.0.1 --port 5178 --strictPort',
    url: 'http://127.0.0.1:5178/tests/fua-print-harness.html',
    reuseExistingServer: true,
    timeout: 120_000,
  },
})
