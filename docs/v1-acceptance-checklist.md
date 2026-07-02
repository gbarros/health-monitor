# V1 Acceptance Checklist

Status: In progress
Created: 2026-07-02

This checklist maps the scoped features from `docs/feature-behavior-spec.md` to implemented evidence, tests, and remaining v1 work. Required items should stay visible here until the final v1 gate is green.

## Feature Evidence Matrix

### F-001: Household And Person Profile

Evidence:
- Service support for households, people, goal profiles, historical targets, and profile-scoped summaries.
- UI profile switching coverage in `tests/unit/test_profile_switch_ui.py`.
- Behavior coverage in `tests/behavior/test_profile_targets.py`.

Remaining:
- Browser e2e must prove setup and two-profile switching in the real Vite app.

### F-002: Food Library

Evidence:
- Food, food version, alias, archive, default-version, and recent-use ranking behavior in the domain/service layer.
- Behavior coverage in `tests/behavior/test_food_version_history.py` and `tests/behavior/test_food_reference_resolution.py`.

Remaining:
- Browser e2e should cover filtering and friendly version context.

### F-003: External Food Lookup

Evidence:
- Local lookup is first, with barcode associations before external providers.
- Open Food Facts adapter supports barcode and Brazil-biased phrase search.
- USDA FoodData Central is optional behind `USDA_ENABLED` and `USDA_API_KEY`.
- Behavior/unit coverage in `tests/behavior/test_food_lookup_candidates.py` and `tests/unit/test_usda_lookup_provider.py`.

Remaining:
- Add recorded Open Food Facts fixtures and optional live smoke tests.
- Expand controlled source ranking tests across local, OFF, USDA, research, and estimate fallback.

### F-004: Today Diary

Evidence:
- Diary entries are grouped by inferred/editable meal type and calculated deterministically from stored food versions.
- Behavior coverage in `tests/behavior/test_daily_driver_application_slice.py`.

Remaining:
- Browser e2e should cover edit/delete states on the real daily-driver screen.

### F-005: Manual Meal Logging

Evidence:
- Manual quick custom food and known-food meal logging are available through service and HTTP API paths.
- Behavior coverage in `tests/behavior/test_daily_driver_application_slice.py`.

Remaining:
- Browser e2e should create a food and log a manual meal end to end.

### F-006: Agent Meal Logging From Text

Evidence:
- Deterministic text meal parser drafts proposals, preserves source text, gates writes, and confirms into diary entries.
- Unknown foods can use Ollama estimate fallback through the estimator path.
- Behavior coverage in `tests/behavior/test_agent_text_meal_flow.py`, `tests/behavior/test_unknown_food_estimate_flow.py`, and `tests/behavior/test_proposal_gated_writes.py`.

Remaining:
- Route structured meal drafting through PydanticAI/Ollama when `AGENT_RUNTIME=pydantic-ai`.
- Add strict structured output tests for agent-assisted lookup/clarification.

### F-007: Nutrition Label Or Table Scan

Evidence:
- Label text/table parsing creates proposal-gated food versions with warnings and preserved attachment evidence.
- Barcode evidence can create local barcode associations when confirmed.
- Behavior coverage in `tests/behavior/test_label_scan_proposal_flow.py`, `tests/behavior/test_label_image_extraction.py`, and `tests/behavior/test_barcode_association.py`.

Remaining:
- Improve Brazilian label OCR prompt fixtures and failure-mode coverage.
- Browser e2e should scan/paste label plus barcode and confirm a food version.

### F-008: Recipe And Batch Food Registration

Evidence:
- Recipe proposal flow stores ingredient versions, yield, recipe food version, and immediate portion logging behavior.
- Behavior coverage in `tests/behavior/test_recipe_proposal_flow.py`.

Remaining:
- Add UI and e2e coverage for recipe registration.

### F-009: Free Agent Chat

Evidence:
- Deterministic chat can answer day/week/micronutrient/version questions, draft corrections, draft review notes, and persist chat history.
- PydanticAI/Ollama runtime scaffold exists behind `AGENT_RUNTIME=pydantic-ai`.
- Typed agent tools expose day summary, week summary, weight trend, food resolution, food lookup, food version history, text meal draft, diary correction draft, and review note draft behavior.
- Structured output contracts cover answer, proposal draft, clarification request, and lookup/estimate explanation shapes.
- Behavior coverage in `tests/behavior/test_agent_chat_harness.py`, `tests/behavior/test_diary_entry_corrections.py`, and `tests/behavior/test_review_notes.py`.
- Agent toolkit coverage in `tests/unit/test_agent_toolkit.py` and `tests/unit/test_agent_runtime_scaffold.py`.

Remaining:
- Add optional live Ollama smoke tests for seeded summary and correction drafting.
- Add model-output parsing/eval fixtures for when the live PydanticAI agent chooses draft tools.

### F-010: Weight Log

Evidence:
- Weight entries, source preservation, and trend summaries are implemented.
- Behavior coverage in `tests/behavior/test_weight_and_weekly_review.py`.

Remaining:
- Browser e2e should cover visible weight trend review.

### F-011: Macro And Trend Review

Evidence:
- Day/week totals and target deltas are calculated deterministically.
- UI chart/review coverage exists in `tests/unit/test_review_chart_ui.py`.
- Behavior coverage in `tests/behavior/test_weight_and_weekly_review.py`.

Remaining:
- Browser e2e should verify weekly chart data after diary edits.

### F-012: Micronutrient Side Quests

Evidence:
- Deterministic chat analysis surfaces tracked micronutrient gaps and uncertainty.
- UI coverage in `tests/unit/test_micronutrient_ui.py`.

Remaining:
- Add richer PydanticAI review-note drafting backed by read tools.

### F-013: Attachments And Evidence

Evidence:
- Attachment objects store content, MIME type, byte size, hash, linked record metadata, and retention policy.
- Postgres stores attachment blobs in-table for the deployment target.
- Behavior/unit coverage in `tests/behavior/test_attachments_evidence.py`, `tests/unit/test_postgres_state.py`, and `tests/unit/test_food_evidence_ui.py`.

Remaining:
- Add browser e2e around evidence visibility after label confirmation.

### F-014: Import And Export

Evidence:
- Structured export/import covers app state and validates into an empty service.
- Behavior coverage in `tests/behavior/test_export_import.py`.

Remaining:
- Browser e2e should export and import into an empty state.

### F-015: Background Jobs And Worker

Evidence:
- Durable background jobs include status, payload, result, errors, attempts, and timestamps.
- Worker processes queued text meal, recipe, label, and chat jobs into proposals or answers.
- Behavior/UI coverage in `tests/behavior/test_background_jobs.py` and `tests/unit/test_background_job_ui.py`.

Remaining:
- Browser e2e should queue a background chat job and open the saved answer.

### F-016: Privacy And Deployment

Evidence:
- Frontend never receives provider API keys.
- Per-run agent settings are recorded on agent runs.
- Compose has API, worker, web, and Postgres services with NexusLog-compatible structured logging.
- Runtime config includes `AGENT_RUNTIME`, `MODEL_PROVIDER`, `OPENFOODFACTS_ENABLED`, `USDA_ENABLED`, and `USDA_API_KEY`.
- Tests include `tests/unit/test_agent_settings_ui.py`, `tests/unit/test_compose_runtime.py`, and `tests/contracts/test_nexuslog_event_contract.py`.

Remaining:
- Final Docker health gate must pass after rebuild.
- PydanticAI dependency wiring must be available in the Docker image when runtime is enabled.

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

Remaining:
- Add fixture-backed research-agent adapter tests for restaurant/regional food lookups.
- Add independent enable/disable config for controlled research lookup.

## Required V1 Gate

Evidence:
- `make test`
- `make web-build`
- `make e2e`
- `docker compose up --build -d` with healthy `api`, `worker`, `web`, and `db`

Remaining:
- Add `make e2e` and Playwright workflow coverage.
- Close every required item above or explicitly defer it out of v1.
