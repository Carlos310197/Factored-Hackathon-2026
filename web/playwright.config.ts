import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  use: { baseURL: "http://localhost:3100", trace: "retain-on-failure" },
  webServer: { command: "npm run build && npx next start -p 3100", port: 3100, reuseExistingServer: true, timeout: 180_000,
    env: { E2E_MOCK: "1", DEMO_MODE: "1" } },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1366, height: 860 } } },
    { name: "phone", use: { ...devices["Pixel 7"] }, testMatch: /customer\.spec\.ts/ },
  ],
});
