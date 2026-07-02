import { defineConfig, devices } from "@playwright/test";

const apiPort = process.env.E2E_API_PORT ?? "18765";
const webPort = process.env.E2E_WEB_PORT ?? "15173";
const runId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
const sqlitePath = `data/e2e/playwright-${runId}.sqlite3`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: {
    timeout: 8_000
  },
  use: {
    baseURL: `http://127.0.0.1:${webPort}`,
    trace: "on-first-retry"
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ],
  webServer: [
    {
      command: `PYTHONPATH=src PERSISTENCE_BACKEND=sqlite SQLITE_PATH=${sqlitePath} FOOD_ESTIMATOR=none LABEL_TEXT_EXTRACTOR=none OPENFOODFACTS_ENABLED=false AGENT_RUNTIME=deterministic MODEL_PROVIDER=deterministic python3 -m health_monitor api --host 127.0.0.1 --port ${apiPort}`,
      cwd: "..",
      url: `http://127.0.0.1:${apiPort}/api/health`,
      reuseExistingServer: false,
      timeout: 20_000
    },
    {
      command: `VITE_API_PROXY_PORT=${apiPort} bun run dev -- --host 127.0.0.1 --port ${webPort}`,
      url: `http://127.0.0.1:${webPort}`,
      reuseExistingServer: false,
      timeout: 20_000
    }
  ]
});
