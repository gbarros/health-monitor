import { defineConfig, devices } from "@playwright/test";

const webPort = process.env.AGENT_CHAT_UI_PORT ?? "15273";

export default defineConfig({
  testDir: "./e2e-agent-chat-ui",
  timeout: 30_000,
  expect: {
    timeout: 5_000
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
  webServer: {
    command: `web/node_modules/.bin/vite packages/agent-chat-ui/demo --host 127.0.0.1 --port ${webPort}`,
    cwd: "..",
    url: `http://127.0.0.1:${webPort}`,
    reuseExistingServer: false,
    timeout: 20_000
  }
});
