# Feature Parity Gaps — React Rewrite vs. main

Status: gap review, 2026-07-03. Basis: full inventory of `main:web/src/main.ts` (2,589 lines, ~70 user-facing features) diffed against the current `feature/react-assistant-ui` app.

The backend lost nothing — every endpoint the old app used still exists. The new frontend calls only: households, people, goals, weights, attachments, diary/repeat, and the four agent endpoints. Everything below is frontend work against existing APIs unless marked otherwise.

Guiding principle for restoration: **stay chat-centric**. The chat is the write path; the gaps are almost all *read/inspect/verify* surfaces. Restore them as drawers, sheets, and expandable cards around the chat — not as the old wall of forms.

## Priority 1 — Verification surfaces (the "can I trust what's inside?" gap)

| Gap | Old app had | Backend | Proposed home in new UI |
|---|---|---|---|
| Diary entry edit/delete/undo | Inline qty+meal edit, soft delete with undo | `PATCH /api/diary/{id}`, `DELETE`, `POST .../restore` | Tap an entry in the Day Card → bottom sheet with grams/meal editor, delete + undo toast |
| Day detail per entry | Per-entry version label, source, evidence status, confidence, fiber/sodium | `GET /api/diary/day` (already returns all of it) | Same bottom sheet; Day Card rows get confidence badge like proposal cards |
| Date navigation | Date picker for any past day | `?day=` param already supported | Day Card header: ‹ › arrows + date tap → picker; today is default |
| Proposal inbox | Last 8 proposals w/ status highlight, open-by-tap | `GET /api/proposals` | "Propostas" item in header/drawer → list view; tapping scrolls to/loads the card |
| Proposal audit + agent tool trace | created/confirmed/rejected timestamps, superseded-by links, full tool-call trace w/ errors, fallback reason | All in proposal + agent-run payloads already | "Detalhes" expander on ProposalCard: audit row + tool trace list. This is the trust surface for the model-first architecture — it shows *which* path (model/lookup/estimate) produced each number |
| Food library browser | Accent-insensitive search over name/brand/alias/barcode; per-food nutrients, evidence attachments, default-version badge, last-used, archive | `GET /api/foods`, `POST .../archive`, `GET /api/foods/resolve` | "Alimentos" drawer: search + list; food tap → versions, aliases, label image evidence, archive |
| Weight history + edit | Table of entries w/ inline edit (datetime, kg, note) | `GET /api/weights/trend`, `PATCH /api/weights/{id}` | Tap the weight line on Day Card → sheet with history list + edit |

## Priority 2 — Review & data surfaces

| Gap | Old app had | Backend | Proposed home |
|---|---|---|---|
| Weekly charts | SVG bar chart (daily kcal vs target line) + weight trend line chart | `GET /api/summaries/week`, weights trend | Upgrade `WeekCard` bars to include target line; add weight sparkline (was planned in Phase 5, shipped minimal) |
| Weekly table | Day × (kcal, prot, carb, fat, fiber, sodium, target) | week summary | Expandable table under WeekCard; mobile: swipe tab |
| Review notes list | Title, range, source, body | `GET /api/review-notes` | Section in the review tab/drawer |
| Rolling averages/σ | (new endpoint, built yesterday, no UI) | `GET /api/summaries/rolling` | One line on WeekCard: "média 7d: X kcal ± Y" |
| Export/import | Full JSON export + paste-to-import | `GET /api/exports/full`, `POST /api/imports/full` | Ajustes drawer: "Exportar dados" (download) / "Importar" |
| Manual log & quick-custom food | Log a library food directly; create+log custom food in one form | `POST /api/diary`, `POST /api/diary/custom-food` | Low priority — chat covers this; expose "registrar manualmente" inside the food-library drawer for the escape hatch |
| Food lookup browser | Search OFF/USDA by phrase/barcode, draft version from candidate | `GET/POST /api/lookups/foods` | Inside food-library drawer, "buscar em bases externas" |
| Clarification candidate picker | needs_clarification proposals rendered candidate foods as tappable choices | proposal payload already carries candidates | ProposalCard: render candidates as buttons when status is needs_clarification (today the card is just dead text) |

## Priority 3 — PWA & offline (regression from main + one improvement)

What main actually had (correcting folklore): `service-worker.js` cached the **app shell** (network-first navigation, cache-first statics, `/api/*` never cached); session (household/person/day) persisted in `localStorage` (`health-monitor.session.v1`); and **durable async sends via the server-side job queue** — every agent form had a "background job" toggle: `POST /api/jobs` → worker processes → UI polls every 4s → adopt resulting proposal/chat. A jobs panel showed status/attempts/errors with manual "process" retry. There was no browser-side outbox for offline *sends*; durability came from the server queue.

Current state: manifest + `service-worker.js` still sit in `web/public/` and `index.html` links the manifest, but **nothing registers the worker**; jobs API is completely unused; the model-unavailable replay banner is React state and dies on reload.

Restore + improve:
1. Register the service worker again (`main.tsx`), keep the same shell-cache strategy. Bump cache name.
2. **Persist the replay queue in `localStorage`** (`health-monitor.outbox.v1`): every model-unavailable (503) message and — new — every send that fails on network error gets appended `{person_id, text, created_at}`. On app load and on `online` events, if the queue is non-empty, show the replay banner with the count; replay appends to the thread in order. This gives the browser-persisted replay main never actually had.
3. Re-wire the **background-jobs path** for slow-model sends: optional per the Ajustes drawer ("processar em segundo plano"), plus a jobs sheet (status, attempts, error, adopt-result) using the existing `/api/jobs` endpoints and 4s polling while active. This composes with REQUIRE_MODEL: a queued job survives model downtime server-side and retries.

## Not worth restoring as-is

- The 9-form sidebar layout, mode dropdowns for model settings on every form (now centralized in Ajustes), the separate text-meal/chat/label/recipe forms (chat + the two modals cover them), per-form effort/tool-loop knobs.
- The `late` meal type existed on main; new UI uses 4 meal groups — decide whether to keep `late` (backend still accepts it). Default: fold into `snack` display.

## Suggested implementation order

1. Day Card interactivity: date nav, entry sheet (edit/delete/undo), weight sheet. (P1 core)
2. Proposal inbox + ProposalCard "Detalhes" (audit + tool trace) + clarification candidate picker.
3. Food library drawer (search, versions, aliases, evidence, archive, external lookup).
4. PWA: SW registration + persisted outbox/replay queue.
5. Review surfaces: charts w/ targets, weekly table, review notes, rolling line, export/import.
6. Jobs sheet + background-send option.

Each step is demo-able on its own and none touches the chat write path; verify per the protocol in `docs/ux-redesign-plan.md` §5.
