# Health Monitor

Private household nutrition tracker with deterministic data, proposal-gated agent writes, and a self-contained Docker deployment target.

Current status: planning and bootstrap. The first implementation slices prioritize behavior tests before app code.

## Local Tests

The initial suite uses `unittest` so it can run before dependency installation:

```bash
make test
```

Once dev dependencies are installed, the same tests should be runnable with pytest and parallelized:

```bash
PYTHONPATH=src pytest -n auto
```

## Local API

The current bootstrap API is dependency-light and uses a local SQLite snapshot store by default:

```bash
make dev-api
```

It listens on `http://127.0.0.1:8765` and exposes the first `/api/*` contract used by the tests.

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

The frontend is a Vite SPA without React/Next:

```bash
make web-install
make dev-web
```

Run `make dev-api` in another terminal so Vite can proxy `/api/*`.

## Docker Shape

The Compose topology uses Postgres as the default deployable data store:

```bash
docker compose config
docker compose up --build
```

Services:

- `web`: Vite build served by nginx, public entrypoint on `${WEB_PORT:-8080}`
- `api`: Python API server on the internal Compose network
- `worker`: placeholder background worker process
- `db`: Postgres 17 volume for app state and attachment blobs

For local dependency-light development, `make dev-api` still defaults to SQLite. In Compose, `PERSISTENCE_BACKEND=postgres` stores the application snapshot in Postgres and stores attachment binary content in the `attachment_objects` table as `bytea` rows.
