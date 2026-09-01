import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "list" : [["html", { open: "never" }]],
  timeout: 30_000,
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    // Serves a production build against whatever is in the database.
    //
    // The reset is deliberately NOT run here: `prisma db push --force-reset`
    // is destructive and Prisma gates it behind explicit human consent. Run
    // `npm run db:reset` yourself before the suite to start from the seed.
    command: "npm run build && npm run start",
    url: "http://localhost:3000/today",
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
