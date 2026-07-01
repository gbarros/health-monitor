# Health Monitor Feature And Behavior Spec

Status: Draft
Created: 2026-07-01

## Purpose

This document describes how the app should behave from the user's point of view and from the system's point of view. It is meant to stay practical: each behavior should be understandable, discussable, and eventually testable before implementation.

The current implementation assumption is:

- Backend: Python, FastAPI, PydanticAI.
- Database: Postgres.
- Agent runtime: PydanticAI agents with typed dependencies, typed tools, and structured proposal outputs.
- Frontend: Vite SPA, web-first, mobile-friendly, PWA-oriented.
- Deployment: self-hosted home infrastructure.

## Product Shape

The app has three cooperating surfaces:

- Reading surface: diary, library, charts, reviews, corrections.
- Structured logging surface: fast flows for meals, labels, recipes, and manual entry.
- Free agent chat: flexible assistant for questions, debugging, side quests, and drafting changes.

The agent should feel useful and flexible, but it must not become the source of truth. The source of truth is structured application data.

## Core Rules

### CR-001: Durable Data Is Structured

Food logs, foods, recipes, weights, goals, and review notes are stored as structured records. Chat messages may be stored for audit and continuity, but chat text is not the durable nutrition log.

### CR-002: Agent Writes Go Through Proposals

The agent can draft changes. The app applies changes only after the user confirms them, except for explicitly safe internal records such as saving an agent run trace.

Examples of proposed changes:

- Create diary entries.
- Update diary entry quantity.
- Replace a diary entry's food version.
- Create a food.
- Create a food version.
- Create a recipe.
- Create a review note.

### CR-003: Calculations Are Deterministic

Calories, macros, micronutrients, daily totals, weekly totals, and chart data are calculated by application code from stored records. The model may explain results, but it does not own arithmetic.

### CR-004: Food Versions Are Immutable For Logged History

If a food label changes, the app creates a new food version. Existing diary entries continue pointing at the version used when they were logged unless the user explicitly changes them.

### CR-005: Evidence Is Preserved

When possible, food and diary records should retain evidence:

- Raw user input.
- Uploaded image.
- OCR text.
- External food database source.
- Web source.
- Model estimate note.
- User correction.

### CR-006: Uncertainty Is Visible

The app should show when something is exact, inferred, looked up, estimated, or low confidence. This matters more than making every entry feel artificially precise.

### CR-007: Read Tools Can Be Broad, Write Tools Stay Guarded

The agent may have flexible read access through app tools such as food lookup, diary search, summaries, and trend retrieval. Mutations still go through proposals and confirmation.

### CR-008: User Food Names Are Not Version IDs

The system may use stable internal IDs and immutable food-version IDs, but the user-facing surface should use natural names, aliases, label dates, brands, photos, and "last used" context. Users should not need to think in terms of "Yogurt v17".

## Feature List

### F-001: Household And Person Profile

The app supports a household with one or more people from day one.

Behaviors:

- B-001: A person has a name, timezone, height, weight history, goal profile, and nutrition targets.
- B-002: The active person determines which diary, goals, and recommendations are shown.
- B-003: Goal targets can change over time without rewriting old diary history.
- B-004: If a user changes their calorie or macro target, past daily totals remain the same, but target comparisons use the target active on that date.
- B-124: The UI supports profile switching so family members can use the app without admin/database intervention.

Test candidates:

- Create a person and active goal profile.
- Create two people in one household and switch active profile.
- Change macro targets and verify old diary totals do not change.
- Query a past date and verify the correct historical target is used.

### F-002: Food Library

The food library stores reusable foods for the household.

Behaviors:

- B-005: A food represents a stable identity such as "Greek yogurt", "Minas cheese", or "Homemade lasagna".
- B-006: A food can have multiple versions with different nutrient profiles.
- B-007: One food version can be marked as the default for future logging.
- B-008: A food can be archived without deleting historical diary entries.
- B-009: Searching the library should prefer recent and default foods, but still show older versions when relevant.

Test candidates:

- Create a food with two versions and verify new logs use the default version.
- Archive a food and verify old diary entries still resolve.
- Search for an ambiguous food and verify ranking favors recent/default records.

### F-003: External Food Lookup

The app can search approved external sources when local evidence is insufficient.

Initial approved source categories:

- Local food library.
- Open Food Facts.
- USDA FoodData Central.
- Controlled web lookup.
- Controlled research-agent lookup.
- Model estimate when no better source exists.

Behaviors:

- B-010: Local library matches are preferred when the food is likely the same item.
- B-011: External lookup candidates include source, serving basis, nutrients, and confidence.
- B-012: The app distinguishes branded products from generic foods.
- B-013: A model estimate is labeled as an estimate and should not masquerade as database evidence.
- B-014: A selected external result can create a local food version for future reuse.
- B-015: Barcode lookup, when available, should be treated as stronger evidence than text search.
- B-131: A scanned barcode can be associated with a local food and food version for future matching.
- B-132: If a barcode is already associated locally, future scans should prefer the local associated food/version before external lookup.

Test candidates:

- Search for a known local cheese and verify local result ranks above generic web results.
- Search for a barcode and verify source metadata is preserved.
- Associate a barcode with a local food version and verify future barcode scans resolve locally.
- Fall back to model estimate and verify the estimate is visibly marked.

### F-004: Today Diary

The Today view is the default daily-driver screen.

Behaviors:

- B-016: Diary entries are grouped by meal.
- B-017: Meal names can be inferred from time but remain editable.
- B-018: The day shows total calories, protein, carbohydrates, and fat.
- B-019: Each entry shows quantity, unit, food/version, and confidence/evidence status.
- B-020: Users can edit or delete entries from the day view.
- B-021: Deleting an entry should be reversible through an undo action when practical.

Test candidates:

- Add entries across meal times and verify grouping.
- Edit a quantity and verify totals update deterministically.
- Delete an entry and verify it is removed from totals.

### F-005: Manual Meal Logging

The user can log food without the agent.

Behaviors:

- B-022: User can search foods, choose a version, enter quantity, and save.
- B-023: If the unit requires conversion, the app uses known conversion data or asks for more information.
- B-024: User can create a quick custom food while logging.
- B-025: Manual entries should be marked as high confidence when the food and quantity are explicit.

Test candidates:

- Log 50 g of a known food and verify macros.
- Attempt to log "1 slice" without conversion data and verify the app asks for grams or serving details.
- Create quick custom food and log it in one flow.

### F-006: Agent Meal Logging From Text

The agent converts natural language into proposed diary entries.

Example:

```text
10am, 50g cheese, 2 eggs, coffee with milk
```

Behaviors:

- B-026: The agent parses food names, quantities, units, time, and meal context.
- B-027: The agent uses local food matches first.
- B-028: The agent uses external lookup when local matches are missing or weak.
- B-029: The agent returns a structured proposal with entries, totals, confidence, and evidence.
- B-030: The user can confirm, edit, or reject the proposal.
- B-031: Confirming the proposal creates diary entries.
- B-032: Rejection stores no diary entries.
- B-033: If there is material ambiguity, the agent asks a focused clarification question.
- B-034: If ambiguity is minor, the agent makes a reasonable assumption and labels it.

Test candidates:

- Log a meal with exact quantities and verify proposal shape.
- Log a meal with an ambiguous food and verify local/default matching behavior.
- Log a meal with an unknown food and verify external lookup is attempted.
- Reject a proposal and verify no diary records are created.
- Confirm a proposal and verify entries point at specific food versions.

### F-007: Nutrition Label Or Table Scan

The user can create or update foods from a nutrition label image, OCR text, or pasted table.

Behaviors:

- B-035: The app accepts an image or table-like text.
- B-036: OCR output, if any, is preserved.
- B-037: The agent extracts serving size, nutrients, units, and product identity.
- B-038: The app normalizes nutrients to a canonical basis, usually per 100 g where possible.
- B-039: The user sees parse warnings before saving.
- B-040: Saving a label creates a new food or a new food version.
- B-041: A new label for a known food does not mutate old versions.
- B-042: The user can set the new version as default for future logs.
- B-043: The user can attach the label to a diary entry immediately.
- B-133: If the scan includes barcode evidence, saving the label can create or update a barcode association after user confirmation.

Test candidates:

- Parse a simple nutrition table and verify normalized nutrients.
- Parse a label with serving size only and verify per-serving fields remain explicit.
- Save a new version and verify old diary entries keep their original version.
- Save a label plus barcode and verify barcode resolves to the saved food version later.
- Attach a parsed label to a meal entry and verify evidence link.

### F-008: Recipe And Batch Food Registration

The user can create a reusable food from ingredients and yield.

Behaviors:

- B-044: The agent parses ingredients, quantities, and preparation context.
- B-045: Ingredients are matched to food versions or external sources.
- B-046: The app requires a yield before precise per-gram recipe macros are used.
- B-047: If yield is missing, the recipe can be saved as draft but not used for precise logging.
- B-048: A recipe version stores ingredient versions and yield.
- B-049: Updating a recipe creates a new version rather than changing old logged portions.
- B-050: After saving a recipe, the user can immediately log a portion.

Test candidates:

- Create recipe with explicit yield and verify per-100 g macros.
- Create recipe without yield and verify draft state.
- Update recipe and verify old diary entries still point at old recipe version.

### F-009: Free Agent Chat

The app includes a flexible chat with the nutrition agent.

The chat is not limited to predefined flows. It can answer questions, inspect diary data, explain trends, look up foods, and draft corrections.

Behaviors:

- B-051: The agent can answer questions using app data.
- B-052: The agent can use food lookup and diary query tools as needed.
- B-053: The agent can produce structured proposals from chat.
- B-054: The app requires confirmation before applying proposal changes.
- B-055: The agent should cite which app records or external sources were used when practical.
- B-056: The agent should say when it is estimating or lacks enough evidence.
- B-057: Chat history can be summarized or compacted, but durable records remain separate.

Example questions:

- "Why was yesterday so high in calories?"
- "Did my protein trend improve this week?"
- "What micronutrients look consistently low?"
- "I bought a new cheese. Did we start using the new label?"
- "Help me correct lunch last Friday."

Test candidates:

- Ask a day-summary question and verify the answer is grounded in diary records.
- Ask for a correction and verify the result is a proposal, not an immediate mutation.
- Ask about insufficient data and verify the agent says what is missing.

### F-010: Weight Log

The app tracks weight over time.

Behaviors:

- B-058: User can log weight with date/time and optional note.
- B-059: Weight trend charts should support daily points and rolling trend.
- B-060: Weight data can be used in reviews, but should not overwrite nutrition logs.
- B-061: Future Health Connect or HealthKit imports should create source-tagged records.

Test candidates:

- Log multiple weights and verify trend data.
- Edit a weight entry and verify chart updates.
- Add imported/source-tagged weight and verify source is preserved.

### F-011: Macro And Trend Review

The app provides deterministic charts and agent-assisted explanations.

Behaviors:

- B-062: User can view daily and weekly calories/macros.
- B-063: User can compare actuals against active targets.
- B-064: User can inspect meal-level contribution to totals.
- B-065: Agent explanations should reference deterministic totals.
- B-066: Weekly review should highlight adherence, outliers, and repeated patterns.

Test candidates:

- Generate a weekly macro summary and verify totals.
- Change a diary entry and verify weekly summary changes.
- Ask the agent to explain the week and verify it uses the computed summary.

### F-012: Micronutrient Side Quests

The app supports on-demand exploratory analysis.

Behaviors:

- B-067: The user can ask about likely micronutrient gaps.
- B-068: The agent should distinguish tracked nutrient data from inferred diet pattern analysis.
- B-069: The agent should suggest what data would improve confidence.
- B-070: The agent should avoid medical diagnosis or treatment claims.
- B-071: Side-quest findings can be saved as review notes.

Test candidates:

- Ask for micronutrient analysis with limited data and verify uncertainty is visible.
- Save an agent-generated review note and verify it is linked to source records.

### F-013: Attachments And Evidence

The app stores evidence used for decisions.

Behaviors:

- B-072: User can attach photos to meal logs or food versions.
- B-073: Attachments have metadata: type, source, created time, and linked records.
- B-074: The app can show which attachment supported a food version.
- B-075: Attachments can be retained even if the parsed proposal is rejected.
- B-125: Attachment objects are stored in Postgres by default, with hashes, MIME type, byte size, and linked records.

Test candidates:

- Upload label image and verify attachment record.
- Upload label image and verify blob metadata and hash are stored.
- Reject parse proposal and verify attachment handling follows chosen policy.
- View food version and verify evidence attachment is visible.

### F-014: Import And Export

The user owns their data.

Behaviors:

- B-076: The app can export structured data in a readable format.
- B-077: Export includes foods, versions, diary entries, recipes, weights, goals, and review notes.
- B-078: Export includes enough IDs and timestamps to reconstruct history.
- B-079: Import validates data before writing.
- B-080: Import should not silently overwrite existing records.

Test candidates:

- Export data and verify required record types exist.
- Import valid data into an empty database.
- Import conflicting data and verify conflict handling.

### F-015: Privacy And Deployment

The app is intended for private household use on home infrastructure.

Behaviors:

- B-081: Secrets such as model API keys are not stored in client code.
- B-082: User nutrition and health data stay in the self-hosted database unless explicitly sent to a model or external lookup API.
- B-083: Agent runs record which model/provider was used.
- B-084: External lookup sources should be configurable.
- B-085: The app should support disabling cloud model calls if using local Ollama only.
- B-126: Early versions expose advanced per-run agent knobs such as model profile, effort, max tool loops, and lookup depth.
- B-127: These knobs never expose provider API keys to the browser.
- B-128: Runtime logs use structured events compatible with NexusLog/LogLens.
- B-129: Logs include correlation IDs such as request ID, session ID, job ID, agent run ID, proposal ID, and person ID when relevant.
- B-130: Logs do not include secrets, raw images, full diary content, full model prompts, or provider API keys.

Test candidates:

- Verify model provider is recorded on agent runs.
- Verify external lookup can be disabled in configuration.
- Verify client does not receive provider API keys.
- Change per-run model/effort settings and verify they are stored on the agent run.
- Emit representative API, worker, agent, proposal, and lookup events and verify the NexusLog event shape.

### F-016: Food Reference Resolution

The app should resolve natural user references to the correct food and food version without exposing internal version churn.

Examples:

- "Iogurte Batavo"
- "o leite mais proteico"
- "aquele queijo novo"
- "same breakfast as yesterday"
- "the yogurt I bought this week"

Behaviors:

- B-094: A food can have aliases, nicknames, and phrase handles.
- B-095: Aliases can be scoped to a person, household, or specific food.
- B-096: The resolver uses recency, default version, last logged version, label scan history, brand, barcode, and user wording as ranking signals.
- B-097: The resolver returns candidate matches with reasons, confidence, and the specific food version that would be used.
- B-098: The UI should show friendly labels such as brand, variant, label date, "current default", and "last used yesterday" instead of raw version numbers.
- B-099: The user can correct a bad match, and that correction should become a future resolution signal.
- B-100: Phrases like "new yogurt for this week" can update the default or preferred food version for future logs after confirmation.
- B-101: If two candidates are close enough to materially change macros, the app asks a focused clarification question.

Test candidates:

- Resolve "Iogurte Batavo" to the most recently confirmed Batavo yogurt version.
- Resolve "o leite mais proteico" to the protein-enriched milk after the user has used that phrase before.
- Correct a bad food match and verify the same phrase ranks the corrected food higher later.
- Add a new label for an existing food and verify future vague references prefer the new default while old diary entries remain unchanged.
- Verify the user-facing UI never requires choosing "v2", "v3", or similar version names as the primary label.

### F-017: One-Off ChatGPT History Migration Evidence

The project should support using prior ChatGPT nutrition logs as evidence for feature design, tests, and one-off migration. This does not need to become a polished end-user import surface in the MVP.

Behaviors:

- B-102: The user can place a ChatGPT data export in a local ignored import folder or provide temporary database access for a one-off assisted import.
- B-103: Local tooling can parse exported conversations into candidate diary entries, food aliases, food versions, and test fixtures.
- B-104: Imported ChatGPT-derived records should start as proposals or fixtures, not automatically trusted diary data.
- B-105: The parser should support date-range filtering so the user can focus on the last month.
- B-106: The parser should preserve enough source context to audit why an entry or alias was inferred.
- B-107: The user can redact or exclude sensitive conversations before generating fixtures.
- B-108: If Canvas content is absent or incomplete in the export, the user can manually provide the Canvas/log text as a source artifact.

Test candidates:

- Parse a small synthetic ChatGPT export and extract meal-log candidates.
- Extract repeated food references and produce alias candidates.
- Generate agent fixture cases from real or synthetic logs without writing diary records.
- Verify ignored raw imports are not included in source control.

### F-018: Controlled Research-Agent Lookup

The app may use an external one-off research agent as a lookup source when direct food databases are insufficient.

Example:

```text
Research nutritional references for a KFC Double Crunch combo in Brazil.
Return cited sources, extracted items, uncertainty, and whether the source is official.
```

Behaviors:

- B-114: Controlled research-agent lookup is a source adapter, not a diary mutation path.
- B-115: Research-agent output must be normalized into evidence records before the nutrition agent uses it.
- B-116: Research-agent lookup preserves prompt, sources, timestamps, extracted claims, and confidence.
- B-117: Restaurant or regional food estimates should distinguish official nutrition data, third-party references, and model inference.
- B-118: The app can disable research-agent lookup independently from direct food database lookup.

Test candidates:

- Use a research-agent lookup fixture for a restaurant meal and verify source claims are preserved separately from final estimates.
- Verify disabling research-agent lookup still allows local and direct API lookup.
- Verify a research-agent result cannot create diary entries without a user-confirmed proposal.

## PydanticAI Agent Expectations

The PydanticAI layer should provide flexible chat behavior without requiring us to predefine every possible user intent.

Expected agent pieces:

- A nutrition assistant agent for general chat and logging.
- Typed dependencies containing user/person context, database access services, source configuration, and model settings.
- Read tools for diary, food, source lookup, summaries, and trends.
- Draft tools or structured outputs for proposals.
- Pydantic models for proposal payloads.
- Evals/fixtures for common logging and correction scenarios.

The agent should be allowed to decide when to call read tools. The application should decide when and how proposed writes are applied.

## Proposal Contract

All agent-created data changes should pass through a proposal.

Minimum proposal fields:

- `id`
- `person_id`
- `proposal_type`
- `status`
- `summary`
- `payload`
- `source_agent_run_id`
- `created_at`
- `confirmed_at`
- `rejected_at`
- `applied_record_ids`

Minimum statuses:

- `draft`
- `needs_clarification`
- `confirmed`
- `applied`
- `rejected`
- `superseded`

Proposal behavior:

- B-119: A proposal can be previewed before application.
- B-120: A proposal can be edited before confirmation when the payload type supports editing.
- B-121: Confirming a proposal applies it through normal app services.
- B-122: Applying a proposal is transactional.
- B-123: Rejected proposals remain auditable but do not affect diary totals.

## Meaningful Test Plan Before Coding

Before implementation, we should write fixtures and expected outcomes for the most important flows.

Priority test fixtures:

- T-001: Exact text meal log.
- T-002: Ambiguous food resolved through recent local food.
- T-003: Unknown food resolved through external lookup.
- T-004: New nutrition label creates new food version.
- T-005: Recipe with explicit yield.
- T-006: Recipe missing yield.
- T-007: Past diary correction drafted by chat.
- T-008: Weekly trend explanation grounded in deterministic summary.
- T-009: External lookup disabled.
- T-010: Rejected proposal creates no diary entries.
- T-011: Natural food alias resolved through recency and correction history.
- T-012: ChatGPT export converted into proposed fixtures without diary mutation.

Recommended test layers:

- Unit tests for nutrient math, unit conversion, target selection, and version immutability.
- Service tests for diary writes, food versioning, proposal application, and export/import.
- Agent fixture tests for PydanticAI tools and structured outputs.
- Contract tests for Open Food Facts, USDA, and web lookup adapters.
- End-to-end tests for the full meal logging confirmation flow.

## Open Product Decisions

- Which Vite UI framework should be used?
- Which Brazil-first lookup source should be implemented first after local library and Open Food Facts?
- How much web lookup should be automated versus user-confirmed?
- What chart set is enough for the first daily-driver version?
- What is the first nutrition label parsing path: model vision, OCR plus model, or both?
- What should be the default policy for storing rejected attachments and proposals?
