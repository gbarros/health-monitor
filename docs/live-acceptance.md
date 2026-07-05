# Live Acceptance

Use this checklist for the reviewer-led agent-first acceptance gate on a scratch SQLite database.

## Prep

1. Install Python deps:

```bash
make setup
```

2. Pull the local Ollama models used by the walkthrough and live evals:

```bash
ollama pull ornith:9b
ollama pull qwen3.6:latest
ollama pull glm-ocr:latest
```

3. Seed a disposable scratch database:

```bash
SQLITE_PATH=data/scratch/health-monitor.sqlite3 make seed-scratch-db
```

4. Start the API and worker against the scratch DB:

```bash
SQLITE_PATH=data/scratch/health-monitor.sqlite3 \
OLLAMA_BASE_URL=http://127.0.0.1:11434 \
OLLAMA_MODEL=ornith:9b \
make dev-api
```

5. In another terminal, run the web app:

```bash
make dev-web
```

6. Run the live-model eval gate:

```bash
LIVE_MODEL_TESTS=true \
LIVE_MODEL_NAME=ornith:9b \
OLLAMA_BASE_URL=http://127.0.0.1:11434 \
make test-live-model
```

## Walkthrough

Execute the Gabriel flow from `docs/agent-first-plan.md` section 5.

1. Meal message:
`Almoço: 74g arroz`

Expected:
- Chat produces a proposal, not a direct mutation.
- Proposal tool trace shows structured meal drafting.

2. In-thread follow-up:
`esqueci o pão`

Expected:
- Agent clarifies or drafts an amendment in the thread.
- No legacy direct clarification endpoint is involved.

3. Log-food modal with photo only:

Expected:
- OCR path runs from the attachment.
- Agent asks concise follow-up questions when needed.
- Result is still a proposal, not a direct write.

4. Onboarding conversation on scratch DB:

Expected:
- Agent drafts a `profile_setup` proposal.
- Confirming it creates household, person, and a goal active on the drafted `starts_on` day.

5. Dados and Painel verification:

Expected:
- Proposal history is visible.
- Review notes are visible on the panel when present.
- Diary, goal, and weekly summaries reflect confirmed proposals only.

6. Model-down replay:

Expected:
- Stop Ollama.
- Sending a message returns 503 behavior and persists the outbox replay item.
- Restore Ollama and replay successfully.

## Sign-Off

Record outcomes for each step:

- `pass`: behavior matches the expected result.
- `miss`: file a prompt/tool-description tuning item under `tests/live/` or the relevant docs.

The realignment is only signed off after:

- `make test` passes
- `cd web && bun run build` passes
- `make test-live-model` passes in the reviewer environment
- Gabriel approves the behavior in the app
