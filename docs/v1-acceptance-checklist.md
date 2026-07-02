# V1 Acceptance Checklist

Status: V1 candidate
Created: 2026-07-02

This checklist maps the scoped features from `docs/feature-behavior-spec.md` to implemented evidence, tests, and remaining v1 work. Required items should stay visible here until the final v1 gate is green.

## Feature Evidence Matrix

### F-001: Household And Person Profile

Evidence:
- Service support for households, people, goal profiles, historical targets, and profile-scoped summaries.
- UI profile switching coverage in `tests/unit/test_profile_switch_ui.py`.
- Behavior coverage in `tests/behavior/test_profile_targets.py`.
- Browser e2e setup creates a household, adds two profiles, and verifies person-scoped state after switching.

Remaining:
- None for v1 setup/profile switching.

### F-002: Food Library

Evidence:
- Food, food version, alias, archive, default-version, and recent-use ranking behavior in the domain/service layer.
- Behavior coverage in `tests/behavior/test_food_version_history.py` and `tests/behavior/test_food_reference_resolution.py`.

Remaining:
- None for v1; browser e2e exercises the saved food library through manual logging and recipe/label flows. Richer filtering assertions can improve later UX coverage.

### F-003: External Food Lookup

Evidence:
- Local lookup is first, with barcode associations before external providers.
- Open Food Facts adapter supports barcode and Brazil-biased phrase search.
- USDA FoodData Central is optional behind `USDA_ENABLED` and `USDA_API_KEY`.
- Lookup source ordering composes Open Food Facts before optional USDA.
- Ollama estimate parser preserves calories, macros, fiber, sodium, confidence, and source notes from strict JSON.
- Ollama estimate and label parsers tolerate fenced JSON model output.
- Controlled research lookup has an explicit enable/disable wrapper and fixture-backed regional restaurant coverage.
- Behavior/unit coverage in `tests/behavior/test_food_lookup_candidates.py`, `tests/unit/test_openfoodfacts_lookup_provider.py`, `tests/unit/test_usda_lookup_provider.py`, `tests/unit/test_lookup_config.py`, `tests/unit/test_controlled_research_lookup.py`, and `tests/unit/test_ollama_lookup_parsers.py`.
- Optional live gates exist in `tests/live/` and are run through `make test-live-model` and `make test-cloud-evals`.

Remaining:
- Live OFF smoke remains optional/deferred; fixture-backed OFF coverage is the required v1 gate.

### F-004: Today Diary

Evidence:
- Diary entries are grouped by inferred/editable meal type and calculated deterministically from stored food versions.
- Behavior coverage in `tests/behavior/test_daily_driver_application_slice.py`.
- Browser e2e edits, deletes, and restores diary entries on the real daily-driver screen.

Remaining:
- None for v1.

### F-005: Manual Meal Logging

Evidence:
- Manual quick custom food and known-food meal logging are available through service and HTTP API paths.
- Behavior coverage in `tests/behavior/test_daily_driver_application_slice.py`.
- Browser e2e creates a reusable food and logs a manual diary entry through the Vite app.

Remaining:
- None for v1 manual known-food logging.

### F-006: Agent Meal Logging From Text

Evidence:
- Deterministic text meal parser drafts proposals, preserves source text, gates writes, and confirms into diary entries.
- Unknown foods can use Ollama estimate fallback through the estimator path.
- Behavior coverage in `tests/behavior/test_agent_text_meal_flow.py`, `tests/behavior/test_unknown_food_estimate_flow.py`, and `tests/behavior/test_proposal_gated_writes.py`.
- Browser e2e drafts and confirms a text meal proposal through the Vite app.
- PydanticAI/Ollama routing exists for text meal proposals when `AGENT_RUNTIME=pydantic-ai`, with deterministic proposal creation as the gated write path and fallback metadata on `AgentRun`.
- Unit coverage in `tests/unit/test_live_agent_routing.py` proves live routing, no direct mutation, and fallback recording.
- Container-side live smoke with `ornith:9b` drafted a proposal with no fallback.

Remaining:
- Richer model eval fixtures for ambiguous meal clarification can be added after v1.

### F-007: Nutrition Label Or Table Scan

Evidence:
- Label text/table parsing creates proposal-gated food versions with warnings and preserved attachment evidence.
- Barcode evidence can create local barcode associations when confirmed.
- Ollama Brazilian label OCR parser preserves raw extracted text, warnings, confidence, barcode text, and attachment evidence through the label proposal flow.
- Behavior/unit coverage in `tests/behavior/test_label_scan_proposal_flow.py`, `tests/behavior/test_label_image_extraction.py`, `tests/behavior/test_barcode_association.py`, and `tests/unit/test_ollama_lookup_parsers.py`.
- Browser e2e drafts and confirms a pasted label/table proposal with barcode evidence.
- Browser e2e also attaches image evidence to the label/table proposal.

Remaining:
- None for v1; full OCR-from-image quality remains model-dependent and covered by parser/unit tests plus optional live gates.

### F-008: Recipe And Batch Food Registration

Evidence:
- Recipe proposal flow stores ingredient versions, yield, recipe food version, and immediate portion logging behavior.
- Behavior coverage in `tests/behavior/test_recipe_proposal_flow.py`.
- Browser e2e drafts and confirms a recipe proposal using a saved local food.

Remaining:
- None for v1.

### F-009: Free Agent Chat

Evidence:
- Deterministic chat can answer day/week/micronutrient/version questions, draft corrections, draft review notes, and persist chat history.
- PydanticAI/Ollama runtime scaffold exists behind `AGENT_RUNTIME=pydantic-ai`.
- Typed agent tools expose day summary, week summary, weight trend, food resolution, food lookup, food version history, text meal draft, diary correction draft, and review note draft behavior.
- Structured output contracts cover answer, proposal draft, clarification request, and lookup/estimate explanation shapes.
- Behavior coverage in `tests/behavior/test_agent_chat_harness.py`, `tests/behavior/test_diary_entry_corrections.py`, and `tests/behavior/test_review_notes.py`.
- Agent toolkit coverage in `tests/unit/test_agent_toolkit.py` and `tests/unit/test_agent_runtime_scaffold.py`.
- Live PydanticAI output normalization is covered by `tests/unit/test_agent_output_normalization.py`.
- Container-side live smoke with `ornith:9b` answered a seeded structured diary question through PydanticAI/Ollama with no fallback.

Remaining:
- Broader correction/review live eval sets are deferred; deterministic proposal tooling and live text-meal smoke cover the required v1 mutation guard.

### F-010: Weight Log

Evidence:
- Weight entries, source preservation, and trend summaries are implemented.
- Behavior coverage in `tests/behavior/test_weight_and_weekly_review.py`.
- Browser e2e adds and edits a weight entry and verifies the visible weight trend chart.

Remaining:
- None for v1.

### F-011: Macro And Trend Review

Evidence:
- Day/week totals and target deltas are calculated deterministically.
- UI chart/review coverage exists in `tests/unit/test_review_chart_ui.py`.
- Behavior coverage in `tests/behavior/test_weight_and_weekly_review.py`.
- Browser e2e verifies weekly chart/review data after diary edits, proposal application, recipe logging, and weight edits.

Remaining:
- None for v1.

### F-012: Micronutrient Side Quests

Evidence:
- Deterministic chat analysis surfaces tracked micronutrient gaps and uncertainty.
- UI coverage in `tests/unit/test_micronutrient_ui.py`.
- PydanticAI read tools expose day/week/weight/food context for future richer side-quest reviews without direct mutation.

Remaining:
- Richer PydanticAI side-quest evals are deferred; deterministic review support remains the v1 fallback.

### F-013: Attachments And Evidence

Evidence:
- Attachment objects store content, MIME type, byte size, hash, linked record metadata, and retention policy.
- Postgres stores attachment blobs in-table for the deployment target.
- Behavior/unit coverage in `tests/behavior/test_attachments_evidence.py`, `tests/unit/test_postgres_state.py`, and `tests/unit/test_food_evidence_ui.py`.
- Browser e2e attaches image evidence during label proposal creation.

Remaining:
- None for v1.

### F-014: Import And Export

Evidence:
- Structured export/import covers app state and validates into an empty service.
- Behavior coverage in `tests/behavior/test_export_import.py`.
- Browser e2e generates an export from the Vite app.
- Browser e2e verifies that importing into a non-empty target is guarded instead of overwriting state.

Remaining:
- Separate-browser empty import e2e is deferred; service-level empty import remains the required v1 correctness gate.

### F-015: Background Jobs And Worker

Evidence:
- Durable background jobs include status, payload, result, errors, attempts, and timestamps.
- Worker processes queued text meal, recipe, label, and chat jobs into proposals or answers.
- Behavior/UI coverage in `tests/behavior/test_background_jobs.py` and `tests/unit/test_background_job_ui.py`.
- Browser e2e queues a background chat job, processes it, and opens the saved answer.

Remaining:
- None for v1 background chat job workflow.

### F-016: Privacy And Deployment

Evidence:
- Frontend never receives provider API keys.
- Per-run agent settings are recorded on agent runs.
- Compose has API, worker, web, and Postgres services with NexusLog-compatible structured logging.
- Runtime config includes `AGENT_RUNTIME`, `MODEL_PROVIDER`, `OPENFOODFACTS_ENABLED`, `USDA_ENABLED`, and `USDA_API_KEY`.
- Runtime config also includes `LIVE_MODEL_TESTS`, `LIVE_MODEL_NAME`, `CLOUD_MODEL_CALLS_ENABLED`, `CLOUD_MODEL_NAME`, and `RESEARCH_LOOKUP_ENABLED`.
- Agent runs record runtime, model name, tool loop count, and fallback reason.
- API Docker image installs the PydanticAI runtime dependency used by the Compose default runtime.
- Docker stack rebuild/start was verified locally with healthy API and DB, running worker/web services, and `/api/health` reachable through the web entrypoint.
- Tests include `tests/unit/test_agent_settings_ui.py`, `tests/unit/test_compose_runtime.py`, and `tests/contracts/test_nexuslog_event_contract.py`.

Remaining:
- None for private-LAN v1 deployment shape.

### F-017: Food Reference Resolution

Evidence:
- Resolver supports aliases, barcode associations, default versions, and recent-use disambiguation without user-facing version IDs.
- Behavior/UI coverage in `tests/behavior/test_food_reference_resolution.py`, `tests/unit/test_food_context_ui.py`, and `tests/unit/test_proposal_food_match_ui.py`.

Remaining:
- Add correction-as-resolution-signal coverage for future ranking.

### F-018: One-Off ChatGPT History Migration Evidence

Evidence:
- ChatGPT history evidence tooling can inspect large exported HTML and extract sanitized signal candidates without durable diary writes.
- Signal extraction supports inferred source dates, date-range filtering, barcode/email redaction, and source-context preservation.
- Raw exports and generated private snippets stay local/ignored.
- Unit coverage in `tests/unit/test_chatgpt_signal_extraction.py` and `tests/unit/test_chatgpt_import_hygiene.py`.

Remaining:
- Add richer candidate payloads for repeated aliases, label/version hints, recipes, and review notes.

### F-019: Controlled Research-Agent Lookup

Evidence:
- Research lookup is modeled as a normalized source adapter and not a mutation path.
- Existing lookup candidate payloads preserve source claims, prompt, confidence, and source metadata.
- Controlled research lookup has fixture-backed enabled/disabled tests for regional restaurant lookup candidates.
- Runtime config includes `RESEARCH_LOOKUP_ENABLED`.

Remaining:
- None for v1; real external research-agent execution remains a future adapter.

## Required V1 Gate

Evidence:
- `make test` passed locally.
- `make web-build` passed locally.
- `make e2e` passed locally.
- `LIVE_MODEL_TESTS=true LIVE_MODEL_NAME=ornith:9b make test-live-model` is wired; host Python skipped because `pydantic_ai` is not installed locally.
- Docker API image import check for PydanticAI passed.
- Container-side live PydanticAI/Ollama smoke with `ornith:9b` passed for seeded chat and text-meal proposal drafting.
- `docker compose up --build -d` passed locally with healthy API/DB, running web/worker, and web-proxied `/api/health`.

Remaining:
- Optional cloud eval with `glm-5.2:cloud` remains opt-in and was not run to conserve credits.
