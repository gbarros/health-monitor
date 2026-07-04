# Agent-First Close-Out Plan

Status: ready for implementation. Branch: `feature/react-assistant-ui`.
Scope: finish the agent-first realignment (`docs/agent-first-plan.md`) — this plan turns its §6 audit findings into implementation phases. Read `agent-first-plan.md` §0 anti-goals before starting; **any new regex/heuristic over user text is out of bounds**, and no new scope beyond these phases.

Working agreement (unchanged from previous plans): one commit per phase; `make test` and `cd web && bun run build` green at every phase boundary; pt-BR UI copy; deterministic runtime is a test double only. The working tree currently has uncommitted changes (see C2) — deal with them first, before anything else.

## Phase C0 — Adopt the in-flight work (do this first)

The tree has uncommitted changes in `src/health_monitor/api/http_api.py` and `tests/contracts/test_http_api_contract.py`: GET-verb support for `/api/agent/chat/stream` (querystring input, `model_profile` shorthand) plus a contract test. Finish it, don't discard it:
- GET requests missing `person_id` or `message` must return 400 (KeyError today — verify the error shape matches other 400s).
- GET carries no `attachment_ids` (already the case) — note it in the route comment: GET exists for `EventSource` clients.
- Check which verb the frontend stream client actually uses (`web/src` fetch of `/api/agent/chat/stream`); if nothing uses GET yet, keep the route (it's the EventSource path for A4 polish) but say so in the test name.
- Commit as its own commit.

Acceptance: `make test` green including the new GET SSE contract test; both verbs covered.

## Phase C1 — Fix the onboarding goal date bug (red test)

`tests/contracts/test_http_api_contract.py::test_onboarding_profile_setup_proposal_applies_household_person_and_goal` fails with `KeyError: 'targets'` — reproduced live: after confirming a `profile_setup` proposal, `GET /api/goals/active?day=<drafted day>` returns `{}`.

Root cause: `_apply_profile_setup_proposal` (service.py ~line 4835) sets `starts_on=date.today()` **at confirm time**. Confirmation can happen on a later day than the conversation (or a test can straddle midnight), leaving the drafted day without an active goal. This violates the date rule from the wrong side: apply must be deterministic w.r.t. the proposal, not the wall clock.

Fix:
1. `draft_onboarding_proposal` (service.py ~4098): include `"starts_on": <drafting day ISO>` in the proposal payload. The drafting day comes from the onboarding session context (the `today` the client sent, falling back to server date at draft time).
2. `_apply_profile_setup_proposal`: `starts_on=date.fromisoformat(payload["starts_on"])`, falling back to `date.today()` only when the payload lacks the key (old snapshots).
3. Update the contract test to read `starts_on` from the proposal payload and query `goals/active` with that day — no hardcoded dates anywhere in it.
4. Add one behavior test: draft on day D, confirm with a later "today", goal is active on D.

Acceptance: `make test` green regardless of calendar date (sanity-check by grepping the test for hardcoded `2026-` dates — there must be none that the assertion depends on).

## Phase C2 — Dev environment runs the real product

`pyproject.toml` already declares `pydantic-ai>=0.7`, but the dev environment was never synced — `import pydantic_ai` fails, so every chat 503s locally and the agent loop has never been exercised on this machine. Nobody can accept what nobody can run.

1. Sync the env as part of setup: add a `make setup` (or extend an existing target) that installs the project deps into the active environment (match however the repo is currently run — `PYTHONPATH=src` suggests no editable install; `pip install -e .` or `uv sync` — pick one, document it in README's dev section, and make `make dev-api` fail fast with a clear message if `pydantic_ai` is missing while runtime is model-backed).
2. Flip the server default: `config.py` `agent_runtime` env default `"deterministic"` → `"pydantic-ai"`. This affects **server boot only** (`load_config`); tests construct `HealthMonitorService(...)` directly with the constructor default (`deterministic`), which stays as is — verify no test reads `load_config` for runtime.
3. Boot log line: when runtime is model-backed, log model name + Ollama URL + whether `pydantic_ai` imported, so a misconfigured env is visible in the first second of `make dev-api`.
4. Confirm `compose.yaml` images install project deps (they build from pyproject — verify pydantic-ai lands in the image).

Acceptance: on this machine, after `make setup`: `make dev-api` boots with runtime `pydantic-ai`, and sending "Almoço: 74g arroz" from the UI produces a drafted proposal whose tool trace shows `draft_meal_proposal` (Ollama must be up). With Ollama stopped: 503 + outbox, unchanged.

## Phase C3 — Delete the legacy text-meal path

`propose_text_meal`, `_create_amended_text_meal_proposal`, `parse_text_meal_amendment`, and the message-parsing role of `parse_text_meal_items` survive with tests as their only callers (~25 call sites: `test_agent_text_meal_flow.py` (13), `test_unknown_food_estimate_flow.py` (6), `test_export_import.py` (3), plus one each in daily-driver, persistent-state, http-contract, nexuslog-contract). This dormant footprint is precisely what caused the original drift — remove it so it cannot be re-wired.

1. For each legacy test, decide: does it test **resolution/proposal mechanics** (keep, migrated) or **text parsing** (delete — parsing is the model's job now, covered by live evals):
   - Resolution-chain, estimate, lookup, confirm/apply, export/import, persistence tests: migrate to `service` tool-path equivalents — call the same structured methods the agent tools call (`draft_meal_proposal`-backing service method / `amend_structured_meal_proposal`) with structured items instead of text. Assert the same proposal contents as before (totals, pending versions, evidence, supersede behavior).
   - Pure text-shape tests (heading detection, `-Ng` discounts, `/` separators, "esqueci de incluir" grammar): delete, and make sure the shapes exist in the live eval set (`tests/live/` — added in commit 24ff158; extend it if a shape is missing).
2. Delete the legacy functions and any now-unused helpers (run a dead-code pass: `grep` each `parse_*`/`text_looks_like_*` survivor for remaining callers).
3. Contract/nexuslog tests that only needed *a* proposal: switch them to the structured draft method.

Acceptance: `grep -rn "propose_text_meal\|parse_text_meal_amendment\|text_looks_like" src/` → no hits; `make test` green; test count may drop — list deleted tests in the commit message with the eval-set line covering each.

## Phase C4 — Frontend closures

1. **Clarification UX**: clarification is now conversational. Decide the picker's fate by checking reality: if the agent path can still produce `needs_clarification` proposals with `candidates` (via a tool), keep the `ClarificationPicker` and make picking send a normal chat message ("uso o {food_name}") rather than a direct PATCH; if no production path creates them anymore, delete the picker and the `resolve-food` endpoint. One or the other — no half-wired UI.
2. **Review notes**: verify the review-notes list survived the move from sheets to the Painel page (`GET /api/review-notes`); restore a simple list section on Painel if it was dropped.
3. **Streaming UX**: with a slow model, confirm the thread renders token deltas progressively and shows tool progress lines ("consultando…") from the SSE `tool_call` events; if the adapter buffers until `final`, fix it to yield deltas as they arrive.
4. Sweep for dead code from the realignment: unused api.ts helpers, orphaned components (`ManualInputs.tsx`?), obsolete query keys. Delete, don't comment out.

Acceptance: no dead interactive elements (every visible button does something); streaming visibly streams; `bun run build` clean.

## Gate findings — C5 executed 2026-07-04 (VERDICT: NOT PASSED)

The gate ran live (ornith:9b, scratch DB, 375px). What **passed**: router deletion holds; structured tools draft exact proposals ("Almoço: 74g arroz, 139g feijão" → correct entries/totals via `draft_meal_proposal`); conversation quality is real (agent asked for missing macros in pt-BR, offered defaults); stock thread + markdown render; Chat/Painel/Dados/Ajustes navigation; day strip with date nav; persisted outbox stores failures across reloads; failures are honest in-thread messages; 243 tests green; build clean; seed script works. What **failed** is below — fix in this order, they are one commit each unless noted.

### G1 — BLOCKER: new-household onboarding can never complete
When the agent calls `draft_onboarding_proposal`, the placeholder household id the backend itself injects into deps (`onboarding-household:<session>`) fails `_require_household` → `unknown household_id` → 503. Reproduced live; the agent is even instructed to pass the id when "present". Fix: for new-household sessions pass NO household id into the agent context (say "no existing household — provide household_name"); tools must reject the `onboarding-household:` prefix defensively. Add a behavior test that drives `agent.onboarding()` end-to-end with a scripted FunctionModel **through deps** — the existing contract test calls the tool directly and misses this entire class of bug.

### G2 — BLOCKER: onboarding is stateless
`runtime.onboarding()` sends only the current message — no session history — so the agent forgets the user's name between turns (observed: asked "Qual é o nome da pessoa?" after being told, and echoed the user's message back). Fix: build the onboarding message from all prior session turns (same pattern as `_agent_context_message`), plus a scripted-model test asserting a fact from turn 1 is available in turn 3.

### G3 — BLOCKER: availability probe falsely reports "model unavailable" under load
`_model_available()` probes Ollama `/api/tags` with a 1.5s timeout. While Ollama is busy generating (any concurrent request — one household member mid-meal is enough), the probe times out → every other request 503s. Observed repeatedly; it also silently defeated outbox replay. Fix: the probe should distinguish *unreachable* from *slow* — attempt a plain TCP connect / longer timeout (~10s), cache positive results for ~60s, and never re-probe while a previous agent call in the same process is still running. Simplest robust option: drop the pre-flight probe entirely and let the actual model call fail with a distinct error (see G4) — REQUIRE_MODEL semantics stay intact.

### G4 — MAJOR: every agent exception is labeled "model unavailable"
The G1 `ValueError` surfaced to the user as "Modelo local indisponível" — wrong and misleading. Split the error taxonomy: `model_unavailable` (PydanticAIUnavailable / connection failures) vs `agent_error` (tool/validation/any other exception, message included, HTTP 500). The outbox should only capture `model_unavailable` and network failures; `agent_error` renders in-thread as a real error.

### G5 — MAJOR: streaming is cosmetic
`HttpStreamResponse.events` is a fully prebuilt list — the server runs the whole agent turn, then replays "events" in one flush; the UI shows one giant `text_delta` after minutes of silence, and tool progress shows only the outer `pydantic_ai_chat` call, not the inner resolve/lookup/draft steps. Fix: make the stream handler generator-based (yield SSE frames as they occur), wire pydantic-ai's streaming/tool-event hooks to emit per-tool `tool_call` events and token deltas. With 1–3 minute runs on local models this is a product requirement, not polish. (If pydantic-ai event streaming with Ollama proves hard, minimum viable: emit `tool_call` started/completed events live during the run, and the text in one delta at the end.)

### G6 — MAJOR: shipped default models don't exist in the local Ollama
Backend default `gemma4:e4b` and frontend default `qwen3.6:latest` are both absent from the machine's Ollama (has `ornith:9b`, `qwen3.6:35b`, …) — out of the box, every conversation fails even with Ollama healthy. During the gate the frontend default was patched to `ornith:9b` in the working tree (keep or supersede). Proper fix: frontend sends NO `model_profile` unless the user set one in Ajustes (server default governs); server logs (already added) plus `make smoke-ollama` verify the configured model exists; pick one canonical default that is actually pulled.

### G7 — MAJOR: `make dev-api` is broken
The new preflight heredoc in the Makefile doesn't parse (`syntax error near unexpected token`), so the documented dev command fails for everyone — evidence the implementer never booted the app. Replace the heredoc with a one-liner: `$(PYTHON) -c "import pydantic_ai" || (echo '...run make setup' && exit 1)`. Acceptance: `make dev-api` actually starts the server.

### G8 — PROCESS: the entire close-out implementation is uncommitted
All C0–C4 work sits unstaged/staged in the working tree, violating the one-commit-per-phase agreement (and it nearly got mixed into review edits). Split and commit it (C0 stream, C1 onboarding date fix, C2 env/Makefile, C3 legacy deletion, C4 frontend) before starting on G1.

### G9 — MINOR: latency UX
Meal drafts took 1–3+ minutes on a 9B model with zero feedback (see G5). After G5, also consider: default `max_tool_loops` lower for meal intents, and surfacing the "Tarefas" background path more prominently when a run exceeds ~15s.

## Phase C5 — Live acceptance gate (reviewer-led; implementer prepares)

Implementer prepares, reviewer (Claude, with Gabriel) executes:
- Prep: a seed script or documented steps for a scratch DB (`SQLITE_PATH=...`) with one household/person/goal and a few foods, so the walkthrough doesn't touch real data; `make test-live-model` runnable and documented (which model tags must be pulled).
- The gate is `agent-first-plan.md` §5 (the Gabriel test), executed with the real model:
  1. meal message → tool-drafted proposal; 2. "esqueci o pão" → clarify or amend in-thread; 3. log-food modal, photo only → OCR → follow-up questions → draft; 4. onboarding conversation → profile_setup card → confirm; 5. Dados/Painel data checks; 6. model stopped → 503 + persisted outbox replay.
- Every miss is filed as a prompt/tool-description tuning item in `tests/live/` — never as routing code.

Exit criterion for the whole realignment: §5 passes live, `make test` green, and Gabriel signs off in the app, not in the diff.
