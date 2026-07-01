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

## Local Web

The frontend is a Vite SPA without React/Next:

```bash
make web-install
make dev-web
```

Run `make dev-api` in another terminal so Vite can proxy `/api/*`.

## Docker Shape

The first Compose topology is present:

```bash
docker compose config
docker compose up --build
```

Services:

- `web`: Vite build served by nginx, public entrypoint on `${WEB_PORT:-8080}`
- `api`: Python API server on the internal Compose network
- `worker`: placeholder background worker process
- `db`: Postgres 17 volume for the upcoming durable repositories

The current API service persists a full application snapshot to SQLite through a repository boundary. Postgres is included in the deployment shape so the next implementation slice can replace the snapshot backend with normalized Postgres repositories without changing the API/UI behavior.
