# Agent-First Realignment Plan

Status: approved direction. This plan **supersedes the routing behavior of all previous plans** (`ux-redesign-plan.md`, `restoration-plan.md` §R-phases stay valid as UI inventory, but any instruction there that says "deterministic classifier first, LLM fallback" is dead). Read this document first; on conflict, this wins.

## 0. The misalignment, named

The product is: **an agent you talk to, a database it proposes changes to, and pages where you inspect that database.** Three parts. Everything else is plumbing.

The original scaffold inverted this: a deterministic NL router (regexes for meals, weights, corrections, ranges, review notes, goals, week/day questions) handles messages first, and the LLM is a fallback that most requests never reach. Every subsequent feature grew around that spine, which is why the app keeps drifting away from intent no matter how it's corrected. This plan removes the spine.

**Standing anti-goals — an implementing agent must not reintroduce these:**
1. No deterministic NL interpretation of user messages. Regex/heuristics never decide what the user *meant*. (Single sanctioned exception: §2.4 weight quick-log.)
2. Modes are never forms that call dedicated endpoints. They are **prompt builders** that compose a chat message; the agent does the rest.
3. Clarification is not an error state. It is the agent asking a question in the conversation.
4. The chat is the app's main screen, not a widget in a dashboard. Data inspection lives on separate pages.

What does NOT change: CR-001..008 (`feature-behavior-spec.md`). The LLM never computes nutrients, never writes to the diary, never owns dates. It *interprets* — tools do exact math and draft proposals; the user confirms. Deterministic **calculation** stays; deterministic **interpretation** goes.

## 1. Target architecture

```
user message (chat, or composed by a prompt-builder modal)
  └─ POST /api/agent/chat  { person_id, message, intent?, attachment_ids? }
       └─ pydantic-ai agent (Ollama), multi-turn context:
            - system prompt + intent template (if any)
            - last N chat turns (~10)
            - structured day summaries: last 5 days full, older pruned to 1 line
            - person profile + active goal
          agent loop: read tools → maybe ask a clarifying question (plain text reply)
                      → or call a draft tool → proposal created (status draft)
       └─ response: { message, proposal_id?, behavior_label, run trace }
user confirms proposal → diary/foods/goals change   (unchanged gate)
```

REQUIRE_MODEL stays exactly as is: model down → 503 + persisted outbox replay. The deterministic runtime remains **only** as a test double (`agent_runtime=deterministic` for unit tests); it must not be reachable as a fallback in a model-backed configuration.

## 2. Backend phases

### Phase A1 — Complete the tool belt (before touching the router)

`agent/tools.py` + `runtime.py` already expose read tools (day/week summary, weight trend, food resolution/lookup/version history, label extraction) and some draft tools (text meal, correction, review note, profile, goal). Add the missing write tools, each a thin wrapper over existing service methods:

- `draft_meal_proposal(items: list[{phrase, quantity_g, meal_type?}], day, time?)` — replaces free-text parsing: **the model extracts items into structured args**; the tool resolves foods (library → lookup → estimator), computes nutrients, drafts the proposal. Reuses `_resolve_meal_item_food` and the proposal assembly from `propose_text_meal`, minus its text parsing and minus its internal pydantic-ai recursion.
- `amend_meal_proposal(proposal_id, add: [...], remove: [...], set_quantity: [{entry_id|phrase, quantity_g}])` — structured amendment; merge/supersede math reused from `_create_amended_text_meal_proposal`. The model decides *what* to amend from conversation; the tool does the arithmetic.
- `log_weight(weight_kg, measured_at?)` — direct write (sanctioned, mirrors the manual endpoint).
- `draft_recipe_proposal(name, aliases, ingredients: [{phrase, quantity_g}], total_cooked_weight_g)` — per-100g math in the tool.
- `repeat_meal(source_day, meal_type)`; `draft_range_estimate(label, low_kcal, high_kcal, meal_type?, day?)`.
- `list_open_proposals()` — so the agent knows what's amendable; `get_food_details(phrase)`; `search_foods(query)`.

Tool-level unit tests (deterministic, no model): given structured args → exact proposal contents. This is where the old routing-fixture rigor lives now.

### Phase A2 — Delete the router, make the agent the only door

In `application/service.py` `chat()`:
- **Delete** the deterministic branches: weight parse/log, kcal-range, `text_looks_like_chat_meal_log` → propose_text_meal, quantity-correction, review-note, profile/goal update, capability question, food-version question, micronutrient, week/day reference — all of them. `chat()` becomes: gate (REQUIRE_MODEL) → build context → run agent → persist turn → respond.
- **Delete** (or demote to test-only helpers used by tool tests) the interpretation functions: `text_looks_like_meal_amendment`, `text_looks_like_chat_meal_log`, `parse_chat_weight_entry`, `parse_chat_kcal_range_estimate`, `parse_chat_quantity_correction`, `parse_chat_review_note`, `parse_chat_profile_goal_update`, `parse_chat_*_question`, `parse_text_meal_items`' role as message parser, `chat_default_logged_at`, amendment auto-targeting. Keep pure math/merge helpers that tools call.
- Multi-turn context builder: new `_build_agent_context(person_id, today)` — last ~10 chat turns, pruned day summaries (5 full + older one-liners — exactly the pruning Gabriel manually asked ChatGPT for), profile, active goal, open proposals.
- The agent may reply with **no proposal** (question/answer) — that's the clarification loop. `needs_clarification` proposals stop being auto-generated; the food-candidate disambiguation happens either by the agent asking ("qual iogurte: lean+ ou DS?") or via a `clarify_food_choice` tool that returns candidates the UI renders as tappable options (keep the existing picker UI; picking sends a normal chat message "o lean+").
- Mode endpoints `/api/agent/text-meal`, `/api/agent/label-scan`, `/api/agent/recipe` are **removed from the HTTP surface** once Phase D lands (modals stop calling them). Attachments on chat: image present → agent gets the label-extraction tool result availability; no auto-routing.
- `agent_settings` (model, effort, loops) still flow per request from Ajustes.

Tests: rewrite the chat-harness behavior tests to drive the agent with pydantic-ai's `FunctionModel`/`TestModel` (scripted tool-calling), asserting: meal message → `draft_meal_proposal` called with correctly-shaped args → proposal drafted; ambiguous message → question, no proposal; amend conversation → `amend_meal_proposal`. The 20-shape routing fixture file becomes a **live-model eval set** (`make test-live-model`) instead of unit tests.

### Phase A3 — Intent templates (server side of prompt-builder modals)

- `POST /api/agent/chat` accepts optional `intent: "log_food" | "recipe" | "label_scan" | "weight" | "repeat_meal" | "review"`.
- Server keeps a small registry: intent → extra system-prompt block ("The user opened the *register food* helper. Expect fields like name/brand/portion; any may be missing — ask for what you need, then draft a food-version or meal proposal."). No parsing of the modal text — it's just a well-formatted user message.

### Phase A4 — SSE streaming

- `GET/POST /api/agent/chat/stream`: SSE events `text_delta`, `tool_call` (name + status), `final` (full AgentChatResponse JSON). ThreadingHTTPServer holds the connection per request — acceptable at LAN scale.
- Local models are slow; visible token streaming + "consultando rótulos…" tool progress is what makes the chat feel alive. Non-stream endpoint stays for jobs/tests.

### Phase A5 — Conversational onboarding (first user and every new household member)

The current onboarding is the anti-goal in miniature: a static textarea whose content is regex-parsed (`parseOnboardingMessage` in `web/src/api.ts`) into household/name/targets, hoping the user hit the right keywords. Replace it with a conversation.

Backend:
- **Bootstrap problem**: chat requires a `person_id`, but during onboarding no person exists. Add `POST /api/agent/onboarding-chat` `{ session_id, message, household_id?, hints: { timezone, today, locale } }`:
  - `session_id` is client-generated (UUID in localStorage); the server stores onboarding turns keyed by it (in the snapshot, like chat turns) so the conversation survives reloads.
  - `household_id` present ⇒ "new member joining" flow: the agent knows the household name and existing members, and only needs the new person.
  - Runs the same pydantic-ai agent with an onboarding system block: greet, then steer to lock the essentials — household name (or confirm joining), person name, timezone (offer the browser-hint as default), optional birth date/height/sex/activity, and goals. For goals the agent may *suggest* targets from the stated profile and objective (kcal deficit, g/kg protein — it can reason; the numbers land in a proposal, not directly in the DB). None of the questions are blocking — the user can say "define você" and the agent picks sensible values to propose.
  - Tools available in this mode: `draft_onboarding_proposal(household_name?|household_id, person: {name, timezone, ...}, targets: {...}, notes)` → a `profile_setup` proposal summarizing everything, plus read tools (existing household/people) for the joining flow. **Creation happens only on confirm** — same gate as everything else; confirming applies household+person+goal and returns their ids.
  - On confirm, migrate the onboarding session turns into the new person's chat history so the first conversation is a normal part of the thread.
- REQUIRE_MODEL applies: onboarding needs the model; if it's down the screen says so (503 + retry), no regex fallback.

Frontend (with Phase B):
- The onboarding screen becomes the same stock Thread UI, agent speaking first ("Oi! Vou configurar o diário. Como você se chama, e essa casa já existe aqui?"). The proposal card at the end shows the full profile + goals with Confirmar; confirming boots the app into the normal chat with the same thread.
- "Adicionar pessoa" (person switcher → +) opens the same conversational flow with `household_id` set.
- Delete `parseOnboardingMessage` and the static-textarea screen.

Acceptance: a brand-new user completes setup answering in free-form pt-BR across several turns, receives a profile+goals proposal card, confirms, and lands in chat with that conversation visible in history; a second household member onboards via "+" without re-stating the household; with the model stopped, onboarding refuses with a clear error instead of guessing.

### 2.4 The one deterministic exception
The **Peso** modal keeps calling `POST /api/weights` directly (a number field needs no LLM). In chat, "amanheci com 96,3kg" goes through the agent, which calls the `log_weight` tool. Nothing else earns this exception without Gabriel saying so.

## 3. Frontend phases

### Phase B — A chat that looks like a chat

- Adopt the stock **@assistant-ui/react-ui `Thread`** (already a dependency) with its default styling: bubbles, avatars, markdown rendering (`@assistant-ui/react-markdown`), auto-scroll, running indicator, attachment previews, edit/copy actions, suggestion chips. Delete the custom chat CSS that fights it (`.chat-column` sizing hacks, bubble overrides — see the last two "fix chat" commits for the pain inventory). Accept the library's look; theme only tokens (accent color, radius) via its CSS variables.
- Chat is a **full-screen page**: minimal header (person chip, nav), thread, composer. The Day Card shrinks to a one-line summary strip above the composer or in the header ("706 / 2.000 kcal · Restante 1.294") that links to the Painel page. The full interactive Day Card moves to Painel/Diário.
- ProposalCard remains the tool UI inside the thread (keep `showDetails`, clarification picker → now sends a chat message per §A2). With streaming (A4), render `tool_call` progress inline.
- Suggestion chips over the composer replace QuickActionRow's composer templates: they open the Phase D modals.

### Phase C — Data pages (the canvas, properly)

Real navigation — recommend `react-router` (URL-addressable, works with PWA start_url; tab bar bottom on mobile, top nav desktop): **Chat · Painel · Dados · Ajustes**.

- **Painel** (graphs & stats): interactive Day Card (from R1, with date nav + entry/weight sheets), week bars vs target, 30-day kcal line, macro split, weight trend chart with goal-rate guide, rolling mean ± σ tiles (7d/30d), review notes. Reuse R5 components; add the 30d views (`/api/summaries/week` windows or a small `days=30` extension of `/api/summaries/rolling` which already returns per-day totals).
- **Dados** (raw tables — the "at least let me see the rows" page). Date-range filter shared across tabs:
  - Diary entries (all days in range: datetime, meal, food+version, grams, kcal/macros, source, evidence status, confidence; inline edit/delete/undo via existing endpoints).
  - Weights (edit), Foods & versions (the R3 drawer content as a page: search, versions, aliases, evidence, archive, external lookup), Proposals (all statuses + Detalhes), Jobs, Chat turns.
  - Every table: client-side CSV download. Wide tables scroll inside their container.
  - Backend gap to check: diary listing across a range currently means N× `GET /api/diary/day` — add `GET /api/diary/range?person_id&start&end` returning flat entries if N-day fan-out is too chatty.
- Ajustes page absorbs the settings drawer + export/import (R5) + outbox management.

### Phase D — Modes become prompt builders

One shared mechanic: modal → compose → send to the same thread → agent handles.

- Buttons (chips over composer): **Registrar alimento**, **Receita/lote**, **Rótulo**, **Peso**, **Repetir refeição**.
- Each modal = a few **all-optional** fields + free-text extra + (where relevant) photo attach. Submit composes a readable user message, e.g.:
  ```
  Registrar alimento:
  Nome: requeijão light Tirolez
  Porção consumida: 30g
  (foto do rótulo anexada)
  ```
  and appends it to the thread (`aui.thread().append`) with `intent: "log_food"` and attachment ids. **The modal never calls a draft endpoint.** The agent asks follow-ups in the thread if the info isn't enough, then drafts.
- Peso modal is the §2.4 exception (direct POST). Repetir modal composes "Repetir o almoço de ontem" (+ picker values) — agent calls the `repeat_meal` tool.
- Delete: direct `draftLabelScan`/`draftRecipe`/`draftTextMeal` calls from the UI, then (with A2) the endpoints.

## 4. Order & dependencies

```
A1 tools ──► A2 router deletion ──► A3 intents ──► D modals ──► cleanup F
                        └─► A5 conversational onboarding (needs A1 agent + B thread)
B stock chat UI (independent — do first for immediate relief)
C data pages   (independent of A — needs only existing read APIs)
A4 streaming   (after A2; before or after D)
```
Suggested sequence for one implementer: **B → C → A1 → A2 → A3+D → A5 → A4 → F**. B and C are pure-frontend quick wins that make the app feel right while the backend inversion (A1/A2, the largest chunk) proceeds. F = delete dead code (router functions, mode endpoints, obsolete unit tests), update `architecture-design.md` to describe the agent-first flow, and mark superseded sections in the older plan docs.

## 5. Acceptance (the Gabriel test)

1. **No hidden determinism**: with the model stopped, *no* chat message of any shape produces a proposal or a write — only 503 + outbox. `grep` shows no `text_looks_like_*` / `parse_chat_*` reachable from `chat()`.
2. **Conversation quality**: "Almoço: 74g arroz / 139g feijão / 113g sobrecoxa / -33g ossos" → agent drafts via tool with exact math; "esqueci o pão" → agent asks "quantas fatias / quantos gramas?" if unsure, then amends the same proposal. All in one continuous thread, in pt-BR, streaming.
3. **Modes**: tapping "Registrar alimento", filling only a photo, sending → agent OCRs, asks whatever's missing, drafts a food version. No form validation ever blocks a send.
4. **Data**: any diary row from any past day is findable, readable (with evidence/confidence), editable, and exportable from Dados; Painel shows kcal-vs-target and weight trend without asking the agent anything.
5. **Chat look**: side-by-side with assistant-ui's demo, the thread is recognizably the same component family (markdown, bubbles, streaming) — not a bespoke square.
6. **Onboarding**: a new user (or new household member) is set up entirely through conversation ending in a confirmable profile+goals proposal — no static form, no keyword guessing.

## 6. Close-out punch list (audit of the implementation, 2026-07-04)

Independent review verdict: the inversion **did land** — `chat()` is gate → context → agent with no routing branches; mode endpoints are gone; prompt-builder modals compose intent-tagged chat messages; onboarding is conversational; the thread is stock `@assistant-ui/react-ui`; pages exist under react-router; SSE streaming is wired. The remaining gaps are below. Each task is small, self-contained, and ordered by severity. Do them in order; do not start new scope.

### T1 — BUG: onboarding goal is not active on the drafted day (test currently red)
`test_onboarding_profile_setup_proposal_applies_household_person_and_goal` fails with `KeyError: 'targets'` because `GET /api/goals/active?day=2026-07-03` returns `{}`: the profile_setup **apply** path stamps the goal's `starts_on` with server-now, and the clock rolled past the drafted day. Reproduced live. Fix: `draft_onboarding_proposal` must capture `starts_on` (the drafting day) in the proposal payload and the apply path must use it — never `date.today()` at confirm time (replay/confirm can happen days later; server-now violates "server owns dates" in the wrong direction). Update the contract test to assert against the payload's `starts_on` rather than a hardcoded date. Acceptance: `make test` green on any calendar day.

### T2 — Finish and commit the in-flight GET SSE work
Working tree has uncommitted changes: `/api/agent/chat/stream` gains GET support (+ contract test). Finish it: GET must reject missing `person_id`/`message` with 400, document that GET is for `EventSource` clients (no attachments), and confirm the frontend actually uses whichever verb it needs. Commit.

### T3 — The product cannot run in the dev environment (why "done" never feels done)
`pydantic_ai` is **not installed** in the local Python env — every chat correctly 503s, so no one (implementer or reviewer) has exercised the real agent loop end-to-end on this machine. Tasks:
- Add `pydantic-ai` to the project's dependency manifest (pyproject/requirements) and README setup steps.
- Flip the server default: `AGENT_RUNTIME` defaults to `pydantic-ai` in `config.py` (deterministic remains available for tests only); `make dev-api` and `compose.yaml` set nothing special.
- Acceptance: fresh checkout + documented setup → send "Almoço: 74g arroz" in the UI → agent drafts a proposal via `draft_meal_proposal` (visible in the tool trace).

### T4 — Delete the quarantined legacy text path
`propose_text_meal` (+ `_create_amended_text_meal_proposal`, `parse_text_meal_amendment`, `parse_text_meal_items`-as-message-parser) survive with ~25 behavior/contract tests as their only callers. This is exactly the footprint that caused the original drift — future agents will find it and re-wire it. Migrate those tests to the tool path (`draft_meal_proposal` / `amend_structured_meal_proposal` with structured args assert the same proposal contents), then delete the legacy functions. Acceptance: `grep -rn "propose_text_meal\|parse_text_meal_amendment" src/` returns nothing.

### T5 — Live-model eval run (the real acceptance)
With T3 done and Ollama up: run `make test-live-model` and walk §5's Gabriel test in the UI (meal → draft; "esqueci o pão" → clarify-or-amend; log-food modal with photo only; onboarding conversation on a scratch DB). File every miss as a prompt/tool-description tuning item — not as new routing code. This is a verification session (reviewer-led), not an implementation task.

### T6 — Small frontend closures
- Confirm needs-clarification candidates picker still works now that clarification is conversational (agent `clarify_food_choice` path) — if the agent asks in plain text only, remove the dead picker or wire it to the tool result.
- Painel: confirm review notes surface survived the page move (was in R5; not found during audit — restore on Painel if dropped).
- Verify streaming UX on a slow model: token deltas render progressively and tool progress lines ("consultando rótulos…") appear; if the foreground still waits for `final`, fix the adapter to consume deltas.

## 7. Verification protocol
Per phase, as established (`ux-redesign-plan.md` §5): `make test` + `bun run build`; live walkthrough at 375×812 **and** desktop width against a scratch DB; live-model eval run (`make test-live-model`) after A2 since routing correctness now lives in the model+tools; adversarial diff review with special attention to anti-goals §0 (any new regex on user text is a finding); REQUIRE_MODEL regression (503 + persisted replay) after every backend phase.
