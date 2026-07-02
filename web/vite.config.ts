import { defineConfig } from "vite";
import { fileURLToPath, URL } from "node:url";

const apiProxyPort = process.env.VITE_API_PROXY_PORT ?? "8765";

export default defineConfig({
  resolve: {
    alias: [
      {
        find: "@health-monitor/agent-chat-ui/styles.css",
        replacement: fileURLToPath(new URL("../packages/agent-chat-ui/src/styles.css", import.meta.url))
      },
      {
        find: "@health-monitor/agent-chat-ui",
        replacement: fileURLToPath(new URL("../packages/agent-chat-ui/src/index.ts", import.meta.url))
      }
    ]
  },
  server: {
    proxy: {
      "/api": `http://127.0.0.1:${apiProxyPort}`
    }
  }
});
