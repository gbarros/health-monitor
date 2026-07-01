**NexusLog vs LogLens**

The app is branded `NexusLog`; this repo’s production wrapper calls the service `loglens`. For implementation, treat the API as NexusLog/LogLens interchangeably.

Local source/docs I used:
[LogLens README](/Users/gabriel/repos/hobby/LogLens/README.md), [API source](/Users/gabriel/repos/hobby/LogLens/src/main.py), [event schema](/Users/gabriel/repos/hobby/LogLens/src/schema.py), [prod wrapper](/Users/gabriel/repos/hobby/home-nas/services/loglens/README.md).

**Best Logging Contract**

Send structured events shaped like this:

```json
{
  "ts": "2026-07-01T12:00:00.000Z",
  "service": "my-client-app",
  "level": "info",
  "event": "checkout.completed",
  "entity_type": "order",
  "entity_id": "ord_123",
  "request_id": "req_abc",
  "session_id": "sess_abc",
  "job_id": "job_abc",
  "payload": {
    "message": "Checkout completed",
    "duration_ms": 243,
    "user_id": "user_123"
  }
}
```

Required fields: `ts`, `service`, `level`, `event`.

`level` must be one of: `debug`, `info`, `warn`, `error`.

Use ISO timestamps, preferably UTC with `new Date().toISOString()`.

Correlation works automatically for:
`entity_type` + `entity_id`, `request_id`, `session_id`, `job_id`, and any string payload key ending in `_id`, such as `user_id`, `document_id`, `order_id`.

**HTTP Ingest API**

Endpoint:

```text
POST /api/events
Authorization: Bearer <ADMIN_TOKEN>
Content-Type: application/json
```

Example:

```bash
curl -X POST http://localhost:4000/api/events \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -d '{
    "ts": "2026-07-01T12:00:00.000Z",
    "service": "my-client-app",
    "level": "info",
    "event": "app.started",
    "payload": { "message": "Application started" }
  }'
```

Successful response:

```json
{ "id": 1 }
```

Minimal TypeScript client:

```ts
type NexusLogLevel = "debug" | "info" | "warn" | "error";

type NexusLogEvent = {
  ts?: string;
  service: string;
  level: NexusLogLevel;
  event: string;
  entity_type?: string;
  entity_id?: string;
  request_id?: string;
  session_id?: string;
  job_id?: string;
  payload?: Record<string, unknown>;
};

export async function logToNexusLog(
  baseUrl: string,
  token: string,
  event: NexusLogEvent,
) {
  const body = {
    ts: new Date().toISOString(),
    ...event,
  };

  const res = await fetch(`${baseUrl.replace(/\/$/, "")}/api/events`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    throw new Error(`NexusLog ingest failed: ${res.status} ${await res.text()}`);
  }

  return res.json() as Promise<{ id: number }>;
}
```

For browser apps, do not ship the production admin token to users. Use this directly only in local dev or from a trusted backend.

**Recommended Dev Setup On This Laptop**

Run NexusLog from the local checkout:

```bash
cd /Users/gabriel/repos/hobby/LogLens
ADMIN_TOKEN=dev-token \
AUTH_DISABLED=false \
DOCKER_ENABLED=false \
CORS_ORIGINS=http://localhost:3000,http://localhost:4000 \
docker compose up -d --build
```

Open:

```text
http://localhost:4000
```

Then your app can post to:

```text
http://localhost:4000/api/events
```

with:

```text
Authorization: Bearer dev-token
```

**Running Alongside Your App With JSONL**

For app development, JSONL tailing is often better than HTTP logging because your app can append events locally and NexusLog tails them.

Add this to your app’s `docker-compose.yml`:

```yaml
services:
  nexuslog:
    build: /Users/gabriel/repos/hobby/LogLens
    image: nexuslog-dev
    ports:
      - "127.0.0.1:4000:4000"
    environment:
      ADMIN_TOKEN: dev-token
      AUTH_DISABLED: "false"
      DOCKER_ENABLED: "false"
      SOURCES: /data/events/my-client-app.events.jsonl
      INGEST_INTERVAL_S: "0.5"
      CORS_ORIGINS: http://localhost:3000,http://localhost:4000
      RETENTION_DAYS: "3"
    volumes:
      - nexuslog_data:/data
      - ./var/nexuslog-events:/data/events:ro

volumes:
  nexuslog_data:
```

Your app writes newline-delimited JSON:

```ts
import { appendFile, mkdir } from "node:fs/promises";
import { dirname } from "node:path";

const eventFile = "./var/nexuslog-events/my-client-app.events.jsonl";

export async function writeNexusEvent(event: NexusLogEvent) {
  const body = {
    ts: new Date().toISOString(),
    ...event,
  };

  await mkdir(dirname(eventFile), { recursive: true });
  await appendFile(eventFile, JSON.stringify(body) + "\n", "utf8");
}
```

Each line must be one complete JSON object matching the same event schema.

**Docker Stdout Option**

If your app runs in Docker, you can also let NexusLog collect stdout:

```yaml
environment:
  DOCKER_ENABLED: "true"
  DOCKER_PARSE: auto
volumes:
  - /var/run/docker.sock:/var/run/docker.sock:ro
```

Then emit structured JSON logs to stdout:

```json
{"level":"info","msg":"job done","request_id":"req_1","job_id":"job_1","user_id":"user_1"}
```

NexusLog stores these as `event: "log.line"` and promotes known fields like `level`, `request_id`, `job_id`, `entity_id`.

If you also ingest the same app through JSONL, set:

```yaml
DOCKER_EXCLUDE_SERVICES: my-client-app
```

to avoid duplicates.

**Useful Read APIs**

List events:

```bash
curl "http://localhost:4000/api/events?service=my-client-app&level=error,warn&limit=50" \
  -H "Authorization: Bearer dev-token"
```

Timeline by entity:

```bash
curl "http://localhost:4000/api/timelines/order/ord_123" \
  -H "Authorization: Bearer dev-token"
```

Stats:

```bash
curl "http://localhost:4000/api/stats?group_by=service&level=error" \
  -H "Authorization: Bearer dev-token"
```

Read-only SQL:

```bash
curl -X POST http://localhost:4000/api/query \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT service, level, event, payload FROM events ORDER BY ts DESC LIMIT 20",
    "limit": 20
  }'
```

**Implementation Guidance**

Use HTTP `POST /api/events` for low-volume, server-side app events.

Use JSONL tailing for local dev, tests, and higher-volume structured event capture.

Use Docker stdout collection when you want zero app-specific integration.

Keep payloads structured and searchable. Put human text in `payload.message`, IDs in `*_id` fields, timings as `duration_ms`, status codes as `status_code`, and error details as `error`, `error_type`, or `stack` as appropriate.

Avoid secrets in payloads. NexusLog stores raw payload JSON in SQLite and exposes it via filters and read-only SQL.