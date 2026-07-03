# UX Redesign Plan — Chat-First Meal Log

Status: approved direction, ready for implementation.
Audience: an implementing agent working on branch `feature/react-assistant-ui`. This document is self-contained; read the referenced files before each phase, and re-read `docs/feature-behavior-spec.md` (CR-001..CR-008) — proposal gating and deterministic calculations remain law.

## 0. Context and evidence

The app replaces a 30-day validated workflow: the user logged meals to ChatGPT in terse Portuguese weighed-item messages and kept totals on a Canvas. Full pattern analysis is in `private/usage-patterns-analysis.md` (local only, do not commit; do NOT open the 33MB HTML export). The essentials that drive every decision below:

- Median log message ~120 chars: `Almoço: / 74g arroz / 139g feijão / 113g sobrecoxa / -33g ossos e pele`. Free text beats forms for logging.
- Almost every meal gets a follow-up patch: "esqueci as duas fatias de pão", "adicione 113g", "subtrai 68g de peixe". Amending the open meal must be first-class.
- Frequent pre-meal budget questions: "quanto ainda tenho hoje?" → totals + remaining vs target must be always visible without asking.
- Recurring named batch foods ("iogurte lean+", "mistura de carne"): total ingredients + total cooked weight → portions logged in grams for weeks.
- "Repita o café da manhã de ontem" — breakfast ~90% identical daily.
- Weigh-ins interleaved: "amanheci com 96.3kgs".
- Restaurant/party meals logged as ranges, refined later by weighing leftovers.
- Primary device is the phone at the table. The ChatGPT Canvas failed on mobile — this was a top pain point. **Mobile-first is mandatory.**
- UI copy: pt-BR (household users are Brazilian). Code, identifiers, comments stay English.

## 1. Target experience (end state)

One continuous chat per person. No mode-switched chat sessions.

**Mobile (primary, ~375px)**: single column —
1. Compact header: app name, person switcher (avatar chips), today's date.
2. **Day Card** (the Canvas replacement): pinned, collapsible. Shows per-meal groups (café/almoço/lanche/janta) with items + kcal, running totals vs active goal (kcal, protein, carbs, fat, fiber), and **remaining budget** prominently. Latest weight + delta. Renders from the API, never from LLM output.
3. Chat thread (persisted history hydrated on load).
4. Quick-action row above the composer: `Repetir refeição` · `Peso` · `Receita/lote` · `Escanear rótulo`.
5. Composer with camera/attachment button.

**Desktop**: two columns — chat left, Day Card + week view right. The current 3-column layout, right-rail panels (Proposals/History/Activity), and mode selector are removed.

**Proposal cards render inline in the chat thread** as the assistant's reply to a log message: editable line items (food match, grams, computed kcal/macros), per-item confidence badge (`exato` / `estimado` / `faixa`), totals, and Confirm/Reject buttons. Confirming updates the Day Card immediately. A follow-up message that amends the meal patches the same draft proposal (superseding it) instead of creating a parallel one.

**Forms only where structure wins** (small modals launched from quick actions):
- Label scan: photo(s) + optional product name/barcode/paste-text.
- Recipe/batch: name + aliases, ingredient lines, total cooked weight.
- Weigh-in: one number field (chat "amanheci com 96.3kg" must also work).
- Repeat meal: picker of yesterday's/recent meals → drafts a proposal with the same items for gram-tweaking.

## 2. Current state (what you build on)

Frontend (`web/`): Vite + React 19 + TypeScript + `@assistant-ui/react` v0.14.
- [App.tsx](web/src/App.tsx) — 3-column shell, onboarding, ProposalPanel/HistoryPanel/ActivityPanel (all to be removed/replaced).
- [useAgentRuntime.ts](web/src/hooks/useAgentRuntime.ts) — `ChatModelAdapter` dispatching by `activeMode` to mode endpoints; returns plain text (proposals summarized as text — to be replaced by tool-call parts, see 3.2).
- [api.ts](web/src/api.ts) — fetch wrappers; [types.ts](web/src/types.ts) — domain types.
- [ModesAndTemplates.tsx](web/src/components/ModesAndTemplates.tsx) — mode buttons + templates (delete in Phase 3).
- Working tree on `feature/react-assistant-ui` has uncommitted changes: **commit the current state as a baseline checkpoint before starting.**

Backend (`src/health_monitor/`): threaded HTTP JSON server ([server.py](src/health_monitor/server.py), routes in [api/http_api.py](src/health_monitor/api/http_api.py), orchestration in [application/service.py](src/health_monitor/application/service.py)). Already exists and works:
- `GET /api/diary/day?person_id&day` → DaySummary (meals grouped, totals, target, target_delta, per-entry `evidence_status` + `confidence`).
- `GET /api/goals/active`, `GET /api/weights/trend`, `POST /api/weights`.
- Proposal lifecycle: draft → confirm/reject/supersede; `PATCH /api/proposals/{id}/entries/{entry_id}` for pre-confirm edits.
- Agent endpoints: `/api/agent/text-meal`, `/api/agent/label-scan`, `/api/agent/recipe` (half-finished), `/api/agent/chat`, `/api/agent/chat-history`.
- Food model: `Food` + immutable `FoodVersion` (per-100g nutrients, confidence, source), `FoodAlias`, barcode associations. Snapshot persistence (SQLite/Postgres) — do not change the persistence model.
- Tests: `tests/` (unittest + behavior/contract). Run with `make test` (or `python -m pytest tests/`).

## 3. Phases

Each phase must end with: backend tests green, `cd web && bun run build` clean (tsc), and the acceptance criteria below demonstrable in the running app. Commit per phase with a clear message. Do not start a phase before the previous one's criteria pass.

### Phase 1 — Mobile-first shell + Day Card

Goal: the Canvas replacement, visible on a phone.

Frontend:
- Rework `App.tsx` layout to the mobile-first single column described in §1; two-column at ≥900px via CSS (restructure `styles.css`; container queries or media queries, no new UI framework).
- New `components/DayCard.tsx`: fetches `GET /api/diary/day` (today, person's timezone — send explicit `day` computed client-side) + `GET /api/goals/active` + `GET /api/weights/trend`. Renders meal groups, totals row, **Restante: X kcal · Yg prot …** line, weight + delta. Collapsible (collapsed shows one-line totals/remaining). Auto-refresh after any proposal confirmation and on person switch.
- Data layer: add `@tanstack/react-query` for fetching/invalidation (queries: `daySummary`, `activeGoal`, `weightTrend`, `chatHistory`, `proposals`). Invalidate on confirm/reject.
- Person switcher moves into the header (chips). Keep `ContextPanel` agent-settings knobs but move them into a settings drawer/modal (gear icon) — they are developer knobs, not daily UI.
- Delete `ActivityPanel` (replace with toast on error only) and `HistoryPanel` (thread history covers it — Phase 2 hydrates it).
- Hydrate the assistant-ui thread from `GET /api/agent/chat-history` on load (map turns to user/assistant message pairs via the runtime's initial messages support).
- PWA basics: `manifest.webmanifest` + icons + theme color so it can be added to the home screen. No service worker/offline.
- UI copy to pt-BR.

Backend: none expected. If DaySummary lacks a field the card needs, extend the serializer, with a behavior test.

Acceptance criteria:
- At 375px width: header, collapsible Day Card, thread, and composer all usable; no horizontal scroll.
- Logging a meal (existing flow) and confirming its proposal updates the Day Card without reload.
- Day Card shows remaining kcal/macros vs target and latest weight with delta.
- Thread shows prior turns after reload.

### Phase 2 — Inline editable proposal cards + open-meal amending

Goal: the confirm loop lives in the chat, and follow-up patches merge.

Frontend:
- Replace the text-only proposal summaries: the `ChatModelAdapter` returns a `tool-call` content part (e.g. tool name `show_proposal`, args = full proposal JSON) alongside a short assistant text; register a `makeAssistantToolUI` component `ProposalCard.tsx` rendering it inline in the thread. (If assistant-ui tool-UI proves brittle with `useLocalRuntime`, fallback: render the active draft proposal in a dock pinned between thread and composer — but try tool UI first, it keeps cards attached to their turn.)
- `ProposalCard` features: line items with food name (+version label), grams (tap-to-edit numeric input → `PATCH /api/proposals/{id}/entries/{entry_id}`), per-item kcal and confidence badge, totals, meal type + time, Confirmar/Rejeitar. After confirm: card flips to applied state, day summary invalidated.
- Status rendering for non-draft states (applied/rejected/superseded — superseded cards collapse with a link to the superseding one).

Backend:
- Amend flow: extend `POST /api/agent/text-meal` with optional `amend_proposal_id`. Behavior: parse the new text as add/remove/replace items relative to the referenced draft proposal, produce a **new draft proposal** containing the merged entry set, mark the old one `superseded` (status exists). Removal grammar must cover the observed patterns: leading `-` ("‑33g ossos"), "subtrai/remove Xg de Y", "adicione Xg de Y", bare item lines = additions.
- Open-meal targeting without explicit id: in the same endpoint, when `amend_proposal_id` is absent and the person has a draft `diary_entries*` proposal for the same day whose latest activity is < 4h old and the text reads as an increment (starts with add/remove verb or `-`, or has no meal-type header), amend that proposal instead of drafting a new one. Deterministic rule, unit-tested — do not delegate this decision to the LLM.
- Behavior tests: add-item amend, remove-item amend, gram-correction amend, new-meal-not-amend (text with a meal header creates a fresh proposal).

Acceptance criteria:
- Log `Almoço: 74g arroz, 139g feijão` → inline card appears; send `esqueci 113g de frango` → the same lunch card is superseded by one with 3 items; confirm → Day Card shows one lunch with 3 items.
- Editing grams on a draft card recomputes item + totals server-side (values come back from the PATCH response, not client math).
- Confidence badges visible per item.

### Phase 3 — One chat, intent routing, quick actions (kill modes)

Goal: the user never selects a mode; the backend routes.

Backend:
- `POST /api/agent/chat` becomes the single conversational entry point: accepts optional `attachment_ids`; routes intent to the existing internal flows (text-meal draft, label-scan, weigh-in, correction/amend, recipe note, plain Q&A). Routing is a deterministic classifier first (regexes/heuristics for the observed message shapes: meal-header lines, `Ng de X` item lists, `NN.Nkg(s)` weigh-ins, attached image → label scan, add/remove verbs → amend), LLM fallback only when heuristics are ambiguous. Weigh-in messages create a weight entry via proposal (`profile_update`-style) or, simpler and acceptable here, a direct weight write with the assistant confirming in text — pick one and test it.
- Response shape unchanged (`AgentChatResponse` with optional embedded proposal) so Phase 2's card rendering just works.
- Keep `/api/agent/text-meal`, `/api/agent/label-scan`, `/api/agent/recipe` as the form-modal endpoints; the chat endpoint calls the same service functions.
- Agent context budget: when building LLM context, include structured day summaries only (last ~5 days full, older pruned to one line) — mirrors what the user manually asked ChatGPT to do.

Frontend:
- Delete `ModesAndTemplates.tsx`, `activeMode` state, mode header, and mode branches in `useAgentRuntime.ts`; the adapter always calls `sendAgentChat` (with uploaded attachment ids when images are attached).
- Quick-action row above the composer: `Repetir refeição`, `Peso`, `Receita/lote`, `Escanear rótulo`. In this phase `Peso` opens the one-field weigh-in modal (POST /api/weights + Day Card invalidation); the other three open placeholders wired in Phases 4–5 (hide until implemented if preferred).

Acceptance criteria:
- With no mode UI anywhere: a pt-BR meal message drafts a meal proposal; `amanheci com 96.3kg` records weight and Day Card updates; a photo of a nutrition label drafts a label proposal; a question ("quanto ainda tenho hoje?") answers from the day summary without drafting anything.
- Routing decisions covered by unit tests over a fixture set of ~20 real message shapes (take them from `private/usage-patterns-analysis.md` §canonical examples; paraphrase, don't commit private text verbatim).

### Phase 4 — Recipe/batch + label-scan modals (finish recipe backend)

Backend:
- Finish `propose_recipe` (service.py ~line 3324): input `{name, aliases[], ingredients: [{text|food_version_id, grams}], total_cooked_weight_g}`. Resolve ingredient nutrients (library → lookup chain → estimator), compute per-100g nutrients of the cooked batch, draft a `recipe_food_version` proposal; confirm creates `Food` + `FoodVersion` (+ `FoodAlias` rows for the given aliases). Behavior tests: the yogurt case (raw ingredients ~950g → cooked 1L, per-100g math) and a cooked-weight-loss case (meat mixture 1183g raw → 530g cooked).
- Label scan already works; ensure `table_text` paste-only (no image) path is solid and the proposal carries extracted-text evidence for display.

Frontend:
- `RecipeModal.tsx`: name, aliases (chips), ingredient rows (text + grams), total cooked weight, submit → proposal card appears in thread (route the created proposal into the same inline rendering path).
- `LabelScanModal.tsx`: photo picker (multi), product name, barcode, optional pasted table text → upload attachments → `draftLabelScan`.
- Both accessible from quick actions; both also reachable when the router in Phase 3 detects the intent in chat (assistant reply includes the draft as usual — modals are conveniences, not the only path).

Acceptance criteria:
- Define "iogurte lean+" via modal with 3 ingredients + total cooked weight → confirm → `Lanche: 120g de iogurte lean+` in chat resolves to it with correct scaled macros.
- Label scan from photo produces a food version whose nutrients match the label (verify against a fixture image); pasted-table path works without any image.

### Phase 5 — Repeat meal, ranges, weekly review

Backend:
- `POST /api/diary/repeat` `{person_id, source_day, meal_type, logged_at_local}` → draft proposal cloning that meal's entries (same food versions, same grams). Test included.
- Range/low-precision entries: allow an entry payload flag `estimate_range: {low_kcal, high_kcal}` (or per-item low/high grams) stored in proposal payload + entry evidence; DaySummary totals use the midpoint and the card shows `~` with the range. Keep scope minimal — observed need is "log a party as a range and move on".
- Review: `GET /api/summaries/week` exists — extend if needed with per-day kcal/macro averages + adherence vs target; add `GET /api/summaries/rolling?days=N` for averages/σ (the user asks for mean and standard deviation explicitly).

Frontend:
- `Repetir refeição` quick action: sheet listing yesterday's + frequent meals (from recent day summaries), tap → repeat proposal card in thread for gram tweaks → confirm.
- Week view on the Day Card's desktop column / a swipe tab on mobile: 7-day bars vs target, weight sparkline (data: week summary + weight trend).
- Range entries render with `~` and a "refinar depois" affordance that pre-fills an amend message.

Acceptance criteria:
- "Repeat breakfast" flow ≤ 3 taps from open app to confirmed meal.
- A party logged as a range shows midpoint totals with visible range marker; later refinement supersedes it.
- Week view shows 7 days of totals vs target and weight trend.

### Phase 6 (optional, defer) — streaming and polish
SSE streaming for chat replies, service-worker offline shell, export/import UX. Do not start without explicit go-ahead.

## 4. Cross-cutting rules

- **Never** let the LLM write to the diary directly; everything durable goes through proposals + confirmation (CR-001..008). Server owns dates/day boundaries — never trust model-produced dates.
- Deterministic before generative: parsing grams/items, amend targeting, intent routing, and all nutrient math are deterministic code with unit tests; the LLM handles food-name resolution fallback, estimates, and conversation only.
- Keep the snapshot persistence and the no-auth LAN posture as-is.
- pt-BR UI copy; number formats accept both `96.3` and `96,3`.
- No new heavyweight deps. Allowed: `@tanstack/react-query`. Anything else: justify in the commit message.
- Don't commit anything from `private/`.

## 5. Verification protocol (performed by a separate reviewing agent)

Per phase, the verifier will:
1. `make test` (backend) and `cd web && bun install && bun run build` — both must pass clean.
2. Launch the stack (api + `bun run dev` via `.claude/launch.json`), resize preview to 375×812, and walk the phase's acceptance criteria exactly as written, in pt-BR, using realistic messages from the analysis doc.
3. Exercise the regression suite of flows from earlier phases (log→confirm→day card, amend, weigh-in).
4. Review the diff for CR violations (direct diary writes, client-side nutrient math, model-owned dates).

Implementer: make this easy — keep acceptance criteria literally demonstrable, and note in each phase's commit message anything that deviates from this plan and why.
