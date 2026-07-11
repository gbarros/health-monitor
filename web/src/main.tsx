import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { ClientErrorBoundary } from "./components/ClientErrorBoundary";
import { installClientTelemetry } from "./clientTelemetry";
import "./styles.css";
import "./tailwind.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
    },
  },
});

installClientTelemetry();

createRoot(document.getElementById("app")!).render(
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <ClientErrorBoundary>
        <App />
      </ClientErrorBoundary>
    </BrowserRouter>
  </QueryClientProvider>,
);

if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {
      // Offline shell is a progressive enhancement; ignore registration failures.
    });
  });
}
