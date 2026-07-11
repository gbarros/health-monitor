import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import tailwindcss from "@tailwindcss/vite";

const apiProxyPort = process.env.VITE_API_PROXY_PORT ?? "8765";
const apiProxyTarget = `http://127.0.0.1:${apiProxyPort}`;
const apiProxy = {
  target: apiProxyTarget,
  // Multimodal runs commonly exceed one minute. Keep the SSE socket open;
  // the backend persists the run independently and remains authoritative.
  timeout: 10 * 60 * 1000,
  proxyTimeout: 10 * 60 * 1000,
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    proxy: {
      "/api": apiProxy,
    }
  },
  preview: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": apiProxy,
    }
  }
});
