import { defineConfig } from "vite";

const apiProxyPort = process.env.VITE_API_PROXY_PORT ?? "8765";

export default defineConfig({
  server: {
    proxy: {
      "/api": `http://127.0.0.1:${apiProxyPort}`
    }
  }
});
