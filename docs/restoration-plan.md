# Restoration Plan — Inspection Surfaces + PWA

Status: superseded where it conflicts with `docs/agent-first-plan.md`.
Keep this document as inspection-surface and PWA inventory. Chat routing,
prompt-builder behavior, model availability, and direct agent endpoint guidance
come from `agent-first-plan.md`.

Audience: an implementing agent on branch `feature/react-assistant-ui`. Self-contained; companion analysis in `docs/feature-parity-gaps.md` (what was lost and why it matters), UX ground rules and verification protocol in `docs/ux-redesign-plan.md` (§1, §4, §5 still apply). Core rules CR-001..008 in `docs/feature-behavior-spec.md` remain law.

## 0. Intent

The React rewrite (chat-first, mobile-first) is the keeper. What it lost vs `main` are the *read/inspect/verify* surfaces and the PWA/offline machinery. Restore those **around** the chat — sheets, drawers, expanders — never as a return to the old form-sidebar layout. The chat remains the only primary write path; every surface below is for verifying, correcting, or recovering.

All backend endpoints needed already exist (the old app used them; the rewrite just stopped calling them). Where a phase says "backend: none", trust it — read `src/health_monitor/api/http_api.py` for the exact contract before writing the client call. Notable payload facts verified in advance:
- `proposal_to_dict` already embeds `agent_run` with `tool_calls` (name, status, input_summary, output_summary, error) — the tool-trace UI needs no backend change.
- `GET /api/proposals?person_id=` lists, `GET /api/proposals/{id}` fetches one.
- Jobs: `POST /api/jobs`, `GET /api/jobs?person_id=`, `GET /api/jobs/{id}`, `POST /api/jobs/{id}/process`.
- Diary: `PATCH /api/diary/{id}`, `DELETE /api/diary/{id}`, `POST /api/diary/{id}/restore`; day summary accepts any `day=`.
- Weights: `PATCH /api/weights/{id}`; foods: `GET /api/foods`, `POST /api/foods/{id}/archive`; lookups: `/api/lookups/foods`; export/import: `/api/exports/full`, `/api/imports/full`; review notes: `GET /api/review-notes`; rolling stats: `GET /api/summaries/rolling?person_id&end&days`.

Working baseline: commit the current tree state before starting (if dirty). One commit per phase, tests green (`make test`) and `cd web && bun run build` clean at each boundary. UI copy pt-BR; numbers accept `,` and `.` decimals. Use the existing react-query setup (`queryKeys.ts`) — every mutation invalidates the queries it affects (`daySummary`, `weightTrend`, `proposals`, `weekSummary`, plus new keys below). No client-side nutrient math beyond display aggregation; edited values come from server responses.

## Phase R1 — Day Card becomes interactive (verify & fix the diary)

Frontend only.
- **Date navigation**: Day Card header gets `‹` / `›` buttons and tap-on-date → native date input. Selected day is App-level state (default today, reset on person switch); DayCard/WeekCard and the chat's `today` param follow it. Past days show the same card (target/delta from that day's goal).
- **Entry sheet**: tapping an entry row opens a bottom sheet (reuse the modal pattern from `WeightModal`/`RecipeModal` in `App.tsx`) showing: food name + brand, version label, source, evidence status + confidence %, full nutrients (incl. fiber/sodium), logged time.
  - Edit: grams (numeric) and meal type (select incl. `late` — backend supports 5 meal types; display label "madrugada") → `PATCH /api/diary/{id}` → invalidate day/week.
  - Delete: `DELETE /api/diary/{id}` → toast with **Desfazer** action (calls `POST /api/diary/{id}/restore`); keep last-deleted id in state, clear on person/day change.
- **Weight sheet**: tapping the weight line on Day Card opens a sheet with the trend list (date, kg, note) from `GET /api/weights/trend`; each row editable (datetime, kg, note) → `PATCH /api/weights/{id}`.

Acceptance: at 375px — navigate to yesterday, edit an entry's grams, see day totals update without reload; delete an entry, undo it, entry returns; edit a weight entry's note. All server-confirmed (values re-render from responses).

## Phase R2 — Proposal trust surfaces

Frontend only.
- **Inbox**: header/drawer item "Propostas" → sheet listing recent proposals (`GET /api/proposals?person_id=`, newest first, status chip highlighted for `draft`/`needs_clarification`, totals line). Tapping a draft opens its full ProposalCard (in the sheet — don't fake-insert into the thread); tapping applied/rejected/superseded shows read-only card.
- **ProposalCard "Detalhes" expander** (collapsed by default) with:
  - Audit: created/confirmed/rejected timestamps; `superseded` cards link to the superseding proposal (`payload.amended_from_proposal_id` / supersede metadata) and load it on tap.
  - Tool trace: `proposal.agent_run.tool_calls` — name (humanized), status badge, input/output summaries, error text in red; plus `agent_run.runtime`, `model_name`, and **`fallback_reason` prominently when non-null** (this is the audit trail for the REQUIRE_MODEL work — if a result ever came from a fallback, it must be visible here).
- **Clarification picker**: when `status === "needs_clarification"` and payload carries unresolved items with `candidates`, render candidates as tappable options (name, brand, version label, kcal/100g, confidence). Picking one calls the same flow main used (`PATCH /api/proposals/{id}/entries/{entry_id}` with the chosen `food_version_id` — check `onClarificationCandidate` in `git show main:web/src/main.ts` lines ~1728-1741 for the exact contract) and re-renders the updated proposal.

Acceptance: a needs-clarification proposal is resolvable by tapping a candidate; a superseded card links to its successor; the trace of a confirmed meal shows which resolver produced each item; a run with `fallback_reason` displays it.

## Phase R3 — Food library drawer

Frontend only.
- Header/drawer item "Alimentos" → full-height drawer: search input (accent- and case-insensitive client filter over name/brand/aliases/barcode — port `normalizeSearch`/`matchesFoodFilter` from main.ts ~2370) over `GET /api/foods?household_id=`.
- Food row: brand + name, default-version badge, per-100g kcal/prot/carb/gord. Tap → detail: all versions (label, nutrients, source, confidence, created), aliases (chips), barcode, label-image evidence (attachment thumbnails via `GET /api/attachments/{id}`), **Arquivar** (`POST /api/foods/{id}/archive`, confirm dialog).
- "Buscar em bases externas": phrase/barcode → `/api/lookups/foods`; candidate rows with source + confidence + "Rascunhar versão" that drafts a food-version proposal (contract: main.ts `onLookupPropose` ~1715).
- Escape hatch: "Registrar manualmente" in the drawer → minimal form (food select or quick-custom via `POST /api/diary/custom-food`, datetime, grams, meal) for when chat is the wrong tool.

Acceptance: search "iogurte" finds foods by alias; a food's versions and label evidence are inspectable; archive removes it from resolution; an external lookup candidate becomes a confirmable proposal.

## Phase R4 — PWA + persisted outbox (the replay that survives reload)

Frontend only.
- **Service worker**: register in `main.tsx` (`navigator.serviceWorker.register("/service-worker.js")`, prod only or guarded). Keep the existing strategy in `web/public/service-worker.js` (shell cache, network-first navigation, never cache `/api/`); bump `CACHE_NAME` to `health-monitor-shell-v2` and add built asset caching on fetch (already cache-first for same-origin GETs — verify it covers hashed `/assets/*`).
- **Persisted outbox** — replaces the React-state replay banner:
  - `localStorage` key `health-monitor.outbox.v1`: array of `{id, person_id, text, created_at, reason: "model_unavailable" | "network"}`.
  - Enqueue on: 503 `model_unavailable` (existing path in `useAgentRuntime`) and on fetch/network failure of a chat send (`TypeError` from fetch — offline).
  - The `ReplayBanner` reads from the outbox (filtered to current person), shows count ("N mensagens aguardando"), and survives reload. Replay sends oldest-first via thread append; each success removes its item; a failure stops the run and keeps the rest. Descartar removes one/all (confirm for all).
  - Auto-prompt: on app load with non-empty outbox, and on `window` `online` event, surface the banner (do not auto-send — the user taps Reenviar; sending meals twice is worse than tapping once).
- **Session**: person/household/selected-day already persist via `STORAGE_KEYS`; extend with selected day.

Acceptance: kill the API mid-session → send a message → error + banner; reload the page → banner still shows the pending message; restart API → tap Reenviar → message processes and outbox empties. App loads its shell with the dev server stopped (SW serves cached shell; data calls fail visibly).

## Phase R5 — Review surfaces

Frontend; tiny backend risk only if week summary lacks fields.
- **WeekCard upgrade**: bars get the per-day target line (week summary `daily_targets`); add weight sparkline (trend endpoint); a "média 7d: X kcal ± Y · Zg prot" line from `GET /api/summaries/rolling`.
- **Weekly table**: expandable under WeekCard (mobile: horizontal-scroll container): day × kcal/prot/carb/gord/fibra/sódio + target kcal.
- **Review notes**: list (title, range, source, body) from `GET /api/review-notes` in the review area.
- **Export/import** in the Ajustes drawer: "Exportar dados" downloads the JSON from `GET /api/exports/full` (client-side blob download, filename `health-monitor-export-<date>.json`); "Importar" file/paste → `POST /api/imports/full` with a destructive-action confirm.

Acceptance: week view shows target line + sparkline + rolling ± line; weekly table matches day summaries; export downloads a JSON containing today's confirmed entries; import into a fresh DB restores them.

## Phase R6 — Background jobs (async sends)

Frontend only.
- Ajustes toggle "Processar em segundo plano" (default off). When on, chat sends go to `POST /api/jobs` (`job_type: "agent_chat"`, payload matching worker contract — read `src/health_monitor/worker.py` + main.ts `onAgentChat` ~1890 for exact payload) instead of the sync endpoint; the assistant replies immediately "Na fila do worker…".
- **Jobs sheet** (header/drawer "Tarefas", badge with active count): rows with type, status, attempts, error; poll `GET /api/jobs` every 4s while any job is `pending`/`running` (react-query `refetchInterval`). Actions: "Processar" (`POST /api/jobs/{id}/process`) for pending jobs, "Abrir resultado" (loads resulting proposal into the R2 sheet, or appends the chat answer to the thread).
- Interplay with REQUIRE_MODEL: a job that fails on model-unavailable stays retryable in the queue — this is the server-side complement to the R4 outbox. Show the error string on the job row.

Acceptance: with background mode on and the model stopped, a sent meal appears as a queued/failed job with a visible error; after the model returns, "Processar" produces a proposal that opens and confirms normally.

## Cross-cutting

- Never write to the diary from these surfaces except through the documented endpoints; proposals stay the only agent write path (CR-001..008).
- New query keys: `proposalsList`, `foods`, `jobs`, `reviewNotes`, `rollingSummary`, `attachments`. Mutations invalidate precisely, not `queryClient.clear()`.
- Sheets/drawers must be usable at 375px: full-width bottom sheets on mobile, side panels ≥900px. No horizontal page scroll ever (tables scroll inside their container).
- Don't grow `App.tsx` unboundedly — new surfaces go in `web/src/components/` (e.g. `DayEntrySheet.tsx`, `ProposalInbox.tsx`, `FoodLibraryDrawer.tsx`, `JobsSheet.tsx`, `outbox.ts` for the queue logic with unit-testable pure functions).
- Outbox logic gets unit tests (enqueue/dedupe/remove/order) — it's the one piece with real correctness risk; test the pure module, not the DOM.

## Verification protocol (per phase, by the reviewing agent)

1. `make test` + `bun run build` clean.
2. Launch via `.claude/launch.json` against a scratch `SQLITE_PATH`, preview at 375×812, walk the phase's acceptance criteria in pt-BR.
3. Regression: log meal → inline card → confirm → Day Card updates; amend flow; weigh-in; REQUIRE_MODEL 503 + replay.
4. R4 specifically: reload persistence and the online-event prompt must be demonstrated, not assumed.
5. Diff review: no direct diary writes, no client nutrient derivation, no new heavyweight deps (anything beyond a headless sheet/drawer primitive needs justification).
