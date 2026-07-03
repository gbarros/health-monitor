import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

const apiProxyPort = process.env.VITE_API_PROXY_PORT ?? "8765";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": `http://127.0.0.1:${apiProxyPort}`
    }
  }
});
