# Health Monitor

Private household nutrition tracker with deterministic data, proposal-gated agent writes, and a self-contained Docker deployment target.

Current status: early daily-driver scaffold. The app has a tested Python API, a Vite SPA, Postgres-backed Docker deployment, a background worker, proposal-gated agent flows, attachment storage, barcode associations, review surfaces, and local/Ollama-assisted lookup paths.

## Local Tests

The initial suite uses `unittest` so it can run before dependency installation:

```bash
make test
```

Once dev dependencies are installed, the same tests should be runnable with pytest and parallelized:

```bash
PYTHONPATH=src pytest -n auto
```

Live-model gates are explicit because they call Ollama-compatible models:

```bash
LIVE_MODEL_TESTS=true LIVE_MODEL_NAME=ornith:9b make test-live-model
```

Cloud model evals are opt-in and should be used sparingly:

```bash
CLOUD_MODEL_CALLS_ENABLED=true CLOUD_MODEL_NAME=glm-5.2:cloud make test-cloud-evals
```

The API Docker image installs `pydantic-ai`; the dependency-light host Python environment may skip live tests if that package is not installed locally.

Private OCR and ChatGPT-export-derived hardening workflows are documented in
`docs/hardening-evals.md`.

## Local API

The current bootstrap API is dependency-light and uses a local SQLite snapshot store by default:

```bash
make dev-api
```

It listens on `http://127.0.0.1:8765`, exposes `/api/health`, and serves the `/api/*` contracts used by the tests.

Local state is written to `data/local/health-monitor.sqlite3`, which is ignored by git.

Unknown foods in text meal proposals can use the local Ollama-compatible estimator:

```bash
OLLAMA_BASE_URL=http://127.0.0.1:11434 OLLAMA_MODEL=gemma4:e4b make dev-api
```

Set `FOOD_ESTIMATOR=none` to disable model estimates. Estimated foods still go through proposals and only become reusable library entries after confirmation.

Nutrition label images can use an Ollama vision model to extract table text when no text is pasted:

```bash
LABEL_TEXT_EXTRACTOR=ollama OLLAMA_VISION_MODEL=llava make dev-api
```

Set `LABEL_TEXT_EXTRACTOR=none` to require pasted table/OCR text. Extracted label text, source, confidence, warnings, and image attachment metadata are preserved on the proposal before any food version is saved.

Food source lookup can query the local library first and Open Food Facts for packaged foods:

```bash
OPENFOODFACTS_ENABLED=true make dev-api
```

Set `OPENFOODFACTS_ENABLED=false` to keep lookup fully local.

## Local Web

The frontend is a Vite SPA without React/Next. It is structured to work as a PWA-compatible app shell where practical:

```bash
make web-install
make dev-web
```

Run `make dev-api` in another terminal so Vite can proxy `/api/*`.

## Browser E2E

The v1 browser workflow uses Playwright against the real Vite app and Python API:

```bash
make e2e
```

The target starts isolated localhost test servers on dedicated ports and stores temporary SQLite state under `data/e2e/`.

## Docker Shape

The Compose topology uses Postgres as the default deployable data store:

```bash
docker compose config
docker compose up --build
```

Services:

- `web`: Vite build served by nginx, public entrypoint on `${WEB_PORT:-8080}`, waits for API health before startup
- `api`: Python API server on the internal Compose network, with `/api/health` healthcheck
- `worker`: background job processor for queued proposal work
- `db`: Postgres 17 volume for app state and attachment blobs

For local dependency-light development, `make dev-api` still defaults to SQLite. In Compose, `PERSISTENCE_BACKEND=postgres` stores the application snapshot in Postgres and stores attachment binary content in the `attachment_objects` table as `bytea` rows.

## Observability

API and worker runtime events are emitted in a NexusLog-compatible JSON shape. By default Compose writes JSON events to stdout with `NEXUSLOG_MODE=stdout`.

Set `NEXUSLOG_MODE=jsonl` to append events to `${NEXUSLOG_JSONL_PATH:-/app/var/nexuslog-events/health-monitor.jsonl}` inside the app data volume. Use `NEXUSLOG_MODE=disabled` to silence app event emission.
