export type ClientTelemetryLevel = "debug" | "info" | "warn" | "error";

export type ClientTelemetryPayload = Record<
  string,
  string | number | boolean | null | readonly string[] | readonly number[]
>;

type ClientEvent = {
  id: string;
  client_ts: string;
  session_id: string;
  page_id: string;
  sequence: number;
  event: string;
  level: ClientTelemetryLevel;
  route: string;
  visibility: string;
  online: boolean;
  payload: ClientTelemetryPayload;
};

const QUEUE_KEY = "health-monitor.client-events.v1";
const SESSION_KEY = "health-monitor.client-session.v1";
const MAX_QUEUE_SIZE = 500;
const BATCH_SIZE = 50;

const sessionId = readOrCreateSessionId();
const pageId = createId("page");
let sequence = 0;
let flushTimer: number | null = null;
let flushPromise: Promise<void> | null = null;
let installed = false;

export function telemetryOperationId(prefix: string): string {
  return createId(prefix);
}

export function telemetryContext(): { sessionId: string; pageId: string } {
  return { sessionId, pageId };
}

export function recordClientEvent(
  event: string,
  payload: ClientTelemetryPayload = {},
  level: ClientTelemetryLevel = "info",
): void {
  const item: ClientEvent = {
    id: createId("event"),
    client_ts: new Date().toISOString(),
    session_id: sessionId,
    page_id: pageId,
    sequence: ++sequence,
    event,
    level,
    route: `${location.pathname}${location.search}`,
    visibility: document.visibilityState,
    online: navigator.onLine,
    payload,
  };
  const queue = readQueue();
  queue.push(item);
  writeQueue(queue.slice(-MAX_QUEUE_SIZE));
  scheduleClientEventFlush();
}

export function flushClientEvents(): Promise<void> {
  if (flushPromise) return flushPromise;
  flushPromise = flushOnce().finally(() => {
    flushPromise = null;
    if (readQueue().length > 0 && navigator.onLine) scheduleClientEventFlush(1_500);
  });
  return flushPromise;
}

export function installClientTelemetry(): void {
  if (installed) return;
  installed = true;
  const navigation = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
  recordClientEvent("client.app.boot", {
    navigation_type: navigation?.type ?? "unknown",
    viewport_width: window.innerWidth,
    viewport_height: window.innerHeight,
    device_pixel_ratio: window.devicePixelRatio,
    user_agent_family: userAgentFamily(),
  });

  window.addEventListener("pageshow", (event) => {
    recordClientEvent("client.lifecycle.pageshow", { persisted: event.persisted });
  });
  window.addEventListener("pagehide", (event) => {
    recordClientEvent("client.lifecycle.pagehide", { persisted: event.persisted });
    void flushClientEvents();
  });
  document.addEventListener("visibilitychange", () => {
    recordClientEvent("client.lifecycle.visibility", { state: document.visibilityState });
    if (document.visibilityState === "visible") void flushClientEvents();
  });
  window.addEventListener("online", () => {
    recordClientEvent("client.lifecycle.online");
    void flushClientEvents();
  });
  window.addEventListener("offline", () => recordClientEvent("client.lifecycle.offline", {}, "warn"));
  window.addEventListener("error", (event) => {
    recordClientEvent(
      "client.error.global",
      {
        error_name: event.error instanceof Error ? event.error.name : "ErrorEvent",
        error_detail: safeErrorDetail(event.error ?? event.message),
        source_line: event.lineno,
        source_column: event.colno,
      },
      "error",
    );
  });
  window.addEventListener("unhandledrejection", (event) => {
    recordClientEvent(
      "client.error.unhandled_rejection",
      {
        error_name: event.reason instanceof Error ? event.reason.name : typeof event.reason,
        error_detail: safeErrorDetail(event.reason),
      },
      "error",
    );
  });
  void flushClientEvents();
}

async function flushOnce(): Promise<void> {
  if (!navigator.onLine) return;
  const batch = readQueue().slice(0, BATCH_SIZE);
  if (batch.length === 0) return;
  try {
    const response = await fetch("/api/client-events/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events: batch }),
      keepalive: true,
    });
    if (!response.ok) return;
    const result = (await response.json()) as { accepted_ids?: string[] };
    const accepted = new Set(result.accepted_ids ?? batch.map((event) => event.id));
    writeQueue(readQueue().filter((event) => !accepted.has(event.id)));
  } catch {
    // The durable queue is intentionally retained for the next lifecycle/online event.
  }
}

function scheduleClientEventFlush(delay = 250): void {
  if (flushTimer != null || !navigator.onLine) return;
  flushTimer = window.setTimeout(() => {
    flushTimer = null;
    void flushClientEvents();
  }, delay);
}

function readQueue(): ClientEvent[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(QUEUE_KEY) ?? "[]");
    return Array.isArray(parsed) ? (parsed as ClientEvent[]) : [];
  } catch {
    return [];
  }
}

function writeQueue(queue: readonly ClientEvent[]): void {
  try {
    localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
  } catch {
    // If storage is full, keep the app interaction usable rather than throwing.
  }
}

function readOrCreateSessionId(): string {
  try {
    const existing = sessionStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const next = createId("session");
    sessionStorage.setItem(SESSION_KEY, next);
    return next;
  } catch {
    return createId("session");
  }
}

function createId(prefix: string): string {
  const suffix = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  return `${prefix}-${suffix}`;
}

function safeErrorDetail(error: unknown): string {
  const detail = error instanceof Error ? error.stack ?? `${error.name}: ${error.message}` : String(error);
  return detail.slice(0, 500);
}

function userAgentFamily(): string {
  const userAgent = navigator.userAgent;
  if (userAgent.includes("Android") && userAgent.includes("Chrome")) return "android-chrome";
  if (userAgent.includes("Android")) return "android-webview";
  if (userAgent.includes("iPhone") || userAgent.includes("iPad")) return "ios-webkit";
  return "desktop-web";
}
