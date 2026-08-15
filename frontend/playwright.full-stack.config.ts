import { defineConfig, devices } from '@playwright/test'

const port = process.env['FULL_STACK_FRONTEND_PORT'] ?? '18080'
const browserChannel = process.env['FULL_STACK_BROWSER_CHANNEL']

export default defineConfig({
  testDir: './e2e/full-stack',
  outputDir: '../artifacts/full-stack-e2e/playwright',
  fullyParallel: false,
  workers: 1,
  forbidOnly: true,
  retries: process.env['CI'] ? 1 : 0,
  timeout: 30 * 60_000,
  expect: { timeout: 30_000 },
  reporter: [
    ['line'],
    ['junit', { outputFile: '../artifacts/full-stack-e2e/playwright-junit.xml' }],
  ],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: {
      mode: 'retain-on-failure',
      screenshots: false,
      snapshots: false,
      sources: false,
    },
    screenshot: 'off',
    video: 'off',
    actionTimeout: 30_000,
    navigationTimeout: 60_000,
  },
  projects: [{
    name: 'chromium',
    use: {
      ...devices['Desktop Chrome'],
      ...(browserChannel ? { channel: browserChannel } : {}),
    },
  }],
})
