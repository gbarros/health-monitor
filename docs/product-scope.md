# Health Monitor Product Scope

Status: Draft
Created: 2026-07-01

## Product Intent

This project exists to replace a long-running ChatGPT nutrition log with a structured app that keeps the convenience of agent-assisted logging while making the source of truth explicit, queryable, and durable.

The app should help a household track nutrition, macro targets, weight trends, and recurring food patterns with less friction than traditional calorie trackers. It should also support exploratory "side quests" such as reviewing micronutrients, social eating patterns, consistency, and correction opportunities.

The product should be deterministic where correctness matters and agentic where friction matters:

- The database is the source of truth.
- Code owns calculations, totals, validation, versioning, and exports.
- The LLM owns parsing, matching, explanation, suggestions, and ambiguity handling.
- The user confirms anything that changes durable records.

## Current Technical Direction

The current default direction is a Python backend using FastAPI and PydanticAI.

PydanticAI should provide:

- Typed agent dependencies.
- Typed read tools for food, diary, lookup, trends, and summaries.
- Structured proposal outputs for app mutations.
- Model-provider flexibility, including Ollama Cloud and local Ollama.
- Agent fixtures and evals for common meal logging, correction, lookup, and review scenarios.

The app should avoid building a large custom agent layer before it is proven necessary. The first agent design should use PydanticAI's existing agent, tool, structured-output, and eval patterns as much as possible.

## Reference Apps And Patterns

### OpenNutriTracker

OpenNutriTracker is the closest UX reference for the reading surface.

Patterns to study and adapt:

- Calendar-driven food diary.
- Meals grouped by breakfast, lunch, dinner, and snack.
- Search, barcode, quick add, custom food, custom meal, and recipe flows.
- Day and week micronutrient views.
- Macro and calorie target visualization.
- Weight history and target trend charts.
- Export/import as a first-class ownership feature.
- Local-first privacy posture.
- Energy unit preferences and flexible user settings.

Main lesson: the app should remain useful even when no agent is involved. The agent improves logistics; it should not be required for basic review, correction, and reporting.

### Waistline

Waistline is most useful as a data integrity and power-user reference.

Patterns to study and adapt:

- Separate the food library from diary entries.
- Preserve historical logs when food labels or recipes change.
- Archive or clone food records instead of mutating old records in place.
- Support serving size and serving count as separate concepts.
- Make tracked nutrients configurable.
- Support both generic foods and branded products.
- Distinguish meals from recipes:
  - A meal is a reusable collection of items that may expand into separate diary entries.
  - A recipe is a prepared dish that can be logged as one reusable food.

Main lesson: a nutrition tracker needs boring, explicit versioning rules. Without them, old logs become unreliable.

### wger

wger is more relevant as a backend and self-hosting reference than as the primary nutrition UX.

Patterns to study and adapt:

- Multi-user support.
- API-first architecture.
- Self-hostable deployment.
- Admin-friendly data management.
- Broader fitness/profile concepts.

Main lesson: household use should be built into both the model and day-one UX, because the app is meant for family use rather than only personal admin use.

## Primary Surfaces

### Reading Surface

This is the normal app experience for reviewing and correcting data.

Expected areas:

- Today diary.
- Calendar diary.
- Meal detail.
- Food library.
- Recipe library.
- Weight log.
- Macro dashboard.
- Weekly review.
- Monthly review.
- Profile and goals.
- Settings and data export.

The reading surface should be calm, dense enough for repeated daily use, and focused on fast scanning. It should avoid becoming a chat transcript.

### Agentic Logging Surface

This is the structured assistant experience for getting real-world food information into the database.

Initial flows:

- Log meal from text.
- Scan nutrition label or table from image/text.
- Resolve foods through web and food-database lookup.
- Register food manually with agent assistance.
- Register recipe or batch-prepped food.
- Ask the agent a fallback question.

Future flows:

- Smart food photo estimation.
- Health Connect or HealthKit context import.
- Micronutrient side-quest analysis.
- Social eating pattern analysis.

The agentic surface should produce structured proposals that the user can confirm, edit, or reject. It should not directly write opaque chat output into the diary.

## Core MVP Scope

The first usable version should include:

- User profile with height, weight, age, sex, activity assumption, goal, and macro targets.
- Food library with food versions.
- Today diary grouped by meals.
- Manual food entry.
- Text-based LLM meal logging.
- Web/API-assisted food lookup for meal parsing and food matching.
- Natural food reference resolution using aliases, recency, and correction history.
- Nutrition label/table parsing from image or pasted text.
- Confirmation workflow before diary writes.
- Recipe or batch-food registration.
- Weight log.
- Macro totals by day and week.
- Basic weekly review.
- Import/export of structured data.

Explicitly deferred:

- Samsung Health / Health Connect sync.
- Apple HealthKit sync.
- Smart plate photo estimation.
- Unbounded autonomous web research outside controlled food-lookup tools.
- Complex family permissions.
- Automated medical or clinical advice.
- Public app-store distribution requirements.

## Agent Input Patterns

### Log A Meal

Goal: convert natural input into a proposed diary entry.

Example input:

```text
10am, 50g cheese, 2 eggs, coffee with milk
```

Expected proposal:

```text
Meal: Breakfast
Time: 10:00

Items:
- Cheese, 50 g, matched to "Minas Cheese v2"
- Eggs, 2 large
- Milk, 60 ml, semi-skimmed

Estimated totals:
- Calories
- Protein
- Carbohydrates
- Fat

Actions:
- Confirm
- Edit quantities
- Use different food
- Save as usual breakfast
```

Important behavior:

- Infer meal name from time, but make it editable.
- Prefer recent foods when a name is ambiguous.
- Use local library matches first, then external food databases or web lookup when local evidence is insufficient.
- Ask for clarification only when the wrong assumption would materially affect the log.
- Preserve the raw user input for auditability.

### Scan A Nutrition Table

Goal: create or update a food version from a label or table.

Inputs may include:

- Nutrition facts image.
- OCR text.
- Table-like pasted text.
- Product name and brand.
- Serving size.
- Barcode, if available.

Expected output:

- A proposed food record.
- A proposed food version.
- Parsed nutrients per 100 g or per serving.
- Source attachment link.
- Confidence and parse warnings.

Important behavior:

- A new label for a known food should create a new version, not overwrite old logs.
- If the user says "new yogurt for this week," future matching should prefer the newest yogurt version.
- The user should be able to attach a label parse to a meal log or save it to the library by itself.
- If a barcode is scanned with the label, the app should create or update a barcode association after confirmation.
- Future scans of that barcode should prefer the confirmed local association before external lookup.

### Register A Recipe Or Batch Food

Goal: create a reusable food from ingredients and yield.

Example input:

```text
I made lasagna for the week with 500g pasta, 700g ground beef,
2 cans tomato sauce, 300g mozzarella, and 200g ricotta.
Final tray is about 2.4kg.
```

Expected output:

- Ingredient list.
- Matched food records and versions.
- Missing assumptions.
- Total recipe macros.
- Macros per 100 g.
- Suggested serving sizes.
- Recipe version.

Important behavior:

- Recipes should be versioned.
- Ingredients should point to specific food versions when possible.
- Yield must be explicit before the recipe is used for precise logging.
- The user should be able to log a portion immediately after saving the recipe.

### Smart Photo Log

Goal: estimate a meal from one or more food photos.

This should not be in the MVP. It is high-value but high-risk because portion estimation is uncertain.

When added, it should produce:

- Identified foods.
- Portion estimates.
- Confidence bands.
- Evidence notes.
- A clear "rough estimate" label unless weighed quantities are supplied.

## Fallback Agent Chat

The app should include a general agent chat powered by PydanticAI. This chat should be broad and useful, not forced through a large set of predefined workflow routes.

The boundary is not "the model can only do predefined things." The boundary is "the model can read, reason, search, and draft freely, but durable app changes go through structured proposals and user confirmation."

Purpose:

- Answer "what happened?" questions.
- Explain totals and trends.
- Help resolve ambiguous logs.
- Suggest corrections.
- Run side-quest analysis.
- Prepare structured proposals for the user to confirm.

Examples:

- "Why was yesterday so high in calories?"
- "Did my protein trend improve this week?"
- "What micronutrients look consistently low?"
- "I bought a new cheese. Did we start using the new label?"
- "Help me correct lunch last Friday."
- "What should I pay attention to socially this weekend?"

Agent runtime requirements:

- The agent can query structured data through typed PydanticAI tools.
- The agent can use approved external food lookup, controlled web lookup, and controlled research-agent lookup.
- The agent can draft changes but cannot commit them without confirmation.
- Every proposed mutation should be represented as structured data.
- The raw prompt, selected context, model response, and final user decision should be auditable.
- The model provider should be swappable, with Ollama Cloud as an expected provider.
- The app should use context retrieval to keep model prompts grounded, but should not overfit the runtime around many rigid request classes.

Minimum tool set for the fallback agent:

- Search foods.
- Search food versions.
- Lookup foods through approved external sources.
- Search diary entries.
- Get day summary.
- Get week summary.
- Get weight trend.
- Draft diary correction.
- Draft new food version.
- Draft recipe.
- Draft review note.

The agent should prefer app-level tools over direct database access. This keeps behavior observable and makes it easier to test without preventing flexible chat.

Food lookup should also be a narrow tool, not free-form browsing. The agent should search approved sources, return candidates with source metadata, and preserve the distinction between local foods, food-database records, controlled research-agent evidence, and model estimates.

Controlled research-agent lookup can be implemented as a source adapter later. For example, a local one-off agent could investigate "KFC Double Crunch combo in Brazil" and return cited claims. That output should be normalized into evidence records before the nutrition agent uses it, and it should never directly mutate diary data.

### Agent Runtime Shape

Each chat turn should roughly follow this shape:

1. Receive the user message and active person context.
2. Let the PydanticAI agent decide whether to answer directly or call tools.
3. Use app tools for diary, food, lookup, trend, and summary retrieval.
4. Return an answer, clarification question, or structured proposal.
5. If there is a proposal, show it to the user for confirmation.
6. Apply confirmed proposals through normal application services.
7. Store the agent run, tool calls, proposal, and final decision.

These labels are useful for tests and analytics, but should not become rigid runtime routes:

- `answer_question`
- `explain_day`
- `explain_week`
- `draft_diary_entry`
- `draft_diary_correction`
- `draft_food_version`
- `draft_recipe`
- `draft_review`

The app may use these labels after the fact to evaluate behavior and improve prompts. The agent should still be free to use relevant read tools as needed.

### Context Bundles

The agent should not receive all diary data by default. It should receive a scoped bundle.

Example context bundle for "Why was yesterday so high in calories?":

- Person profile summary.
- Active goal profile.
- Yesterday's diary entries.
- Yesterday's macro totals.
- Seven-day comparison totals.
- Recent weight trend, if relevant.
- Known high-confidence annotations or corrections.

Example context bundle for "I bought a new cheese. Did we start using the new label?":

- Recent foods matching "cheese".
- Food versions for those foods.
- Recent diary entries using those versions.
- Recent label-scan proposals.
- Default-version history.

Every bundle should have a manifest that records which records were included. This makes model answers debuggable.

### Proposal Lifecycle

The agent can produce proposals, but application services apply them.

Proposal statuses:

- `draft`
- `needs_clarification`
- `confirmed`
- `applied`
- `rejected`
- `superseded`

Example proposal types:

- `create_diary_entries`
- `update_diary_entry_quantity`
- `replace_food_version_for_entry`
- `create_food`
- `create_food_version`
- `create_recipe`
- `create_review_note`

Proposal payloads should be schema-validated before they are shown to the user. Invalid model output is a recoverable parsing error, not an application state change.

### Harness Tests

The fallback agent needs test fixtures early.

Useful fixture categories:

- Meal input with exact quantities.
- Meal input with ambiguous food names.
- New label superseding an older food version.
- Recipe with missing yield.
- Correction to a past diary entry.
- Weekly trend explanation.
- Micronutrient side-quest request.

Each fixture should define:

- Seed records.
- User message.
- Expected behavior label.
- Expected tool calls or context bundle.
- Expected proposal shape.
- Cases where the agent must ask for clarification.

This gives us a way to improve prompts and model providers without manually re-testing common workflows.

## Data Model Seeds

These are not final schema definitions, but they capture the important boundaries.

### Household

Represents a family or shared install.

Likely fields:

- `id`
- `name`
- `created_at`

### Person

Represents an individual tracker inside a household.

Likely fields:

- `id`
- `household_id`
- `name`
- `birth_date`
- `sex`
- `height`
- `current_goal`
- `timezone`

### GoalProfile

Represents the target plan active during a time period.

Likely fields:

- `id`
- `person_id`
- `starts_on`
- `ends_on`
- `daily_calorie_target`
- `protein_target_g`
- `carb_target_g`
- `fat_target_g`
- `notes`

### Food

Represents the stable identity of a food.

Examples:

- "Minas cheese"
- "Greek yogurt"
- "Homemade lasagna"

Likely fields:

- `id`
- `household_id`
- `name`
- `brand`
- `barcode`
- `category`
- `default_version_id`
- `archived_at`

### FoodAlias

Represents a user-facing phrase or nickname for a food.

Examples:

- "Iogurte Batavo"
- "o leite mais proteico"
- "aquele queijo novo"
- "same breakfast cheese"

Likely fields:

- `id`
- `household_id`
- `person_id`
- `food_id`
- `phrase`
- `language`
- `scope`
- `confidence`
- `created_from_agent_run_id`
- `last_used_at`
- `archived_at`

### BarcodeAssociation

Represents a confirmed barcode mapping to a food and, when known, a specific food version.

Examples:

- A yogurt barcode scanned together with its nutrition table.
- A milk barcode that should resolve to the current high-protein milk version.
- A packaged cheese barcode whose label changed over time.

Likely fields:

- `id`
- `household_id`
- `barcode`
- `barcode_format`
- `food_id`
- `food_version_id`
- `source`
- `source_attachment_id`
- `confidence`
- `first_seen_at`
- `last_seen_at`
- `confirmed_at`
- `archived_at`

### FoodVersion

Represents a specific nutrition profile for a food.

Examples:

- "Minas cheese label from June"
- "Minas cheese label from July"
- "Lasagna batch 2026-07-01"

Likely fields:

- `id`
- `food_id`
- `version_name`
- `source`
- `source_attachment_id`
- `serving_quantity`
- `serving_unit`
- `nutrients_per_100g`
- `created_at`
- `valid_from`
- `archived_at`

The user interface should not rely on raw version names like "v2" or "v3". Internal version IDs should remain stable, but the user should see labels such as brand, variant, label date, barcode, "current default", or "last used yesterday".

### FoodResolutionSignal

Represents evidence used to resolve a natural food reference to a food version.

Examples:

- The user corrected "o leite mais proteico" to a specific protein milk.
- The user scanned a new yogurt label and said it was for this week.
- The user logged a Batavo yogurt yesterday.

Likely fields:

- `id`
- `person_id`
- `food_id`
- `food_version_id`
- `phrase`
- `signal_type`
- `source_record_id`
- `weight`
- `created_at`
- `expires_at`

### DiaryEntry

Represents one logged item in a diary.

Likely fields:

- `id`
- `person_id`
- `logged_at`
- `meal_type`
- `food_version_id`
- `quantity`
- `unit`
- `raw_input_id`
- `confidence`
- `notes`

### Recipe

Represents a reusable prepared food.

Likely fields:

- `id`
- `food_id`
- `recipe_version_id`
- `yield_quantity`
- `yield_unit`
- `instructions`

### AgentRun

Represents one model interaction.

Likely fields:

- `id`
- `person_id`
- `purpose`
- `model_provider`
- `model_name`
- `input_summary`
- `context_manifest`
- `output`
- `created_at`

### AgentProposal

Represents structured changes suggested by an agent.

Likely fields:

- `id`
- `agent_run_id`
- `proposal_type`
- `payload`
- `status`
- `confirmed_at`
- `rejected_at`
- `applied_record_id`

## Product Principles

- Start with daily-driver reliability before advanced intelligence.
- Keep manual correction fast.
- Preserve old data when foods change.
- Prefer explicit user confirmation over hidden automation.
- Make exports boring and readable.
- Treat nutrition and health data as private by default.
- Keep agent prompts small and grounded in structured retrieval.
- Make uncertainty visible.
- Do not let chat become the permanent storage format.
- Keep immutable food-version IDs internal; give users natural names, aliases, label dates, and recency context.

## Open Questions

- Should the first app be mobile-first, web-first, or a PWA with later native companions?
- Should data be local-first with optional sync, or server-first from day one?
- What database should be used for the first implementation?
- Which Brazil-first lookup sources should be enabled first, and how should local, Open Food Facts, Brazilian reference tables, USDA fallback, web, research-agent, and model-estimated matches be ranked?
- Should controlled research-agent lookup be supported as a source adapter, and which agent runtimes are acceptable for it?
- What is the minimum viable agent provider abstraction for Ollama Cloud plus future providers?
- What is the simplest day-one family profile switching UX?
- How should photos and nutrition-label attachments be stored?
- How should prior ChatGPT logs be imported, redacted, and converted into fixtures or proposals?
- What is the initial review cadence: daily, weekly, monthly, or on demand?

## Near-Term Planning Tasks

- Define the first end-to-end user journey.
- Decide the application stack.
- Draft the first database schema.
- Draft the agent tool contract.
- Draft the model response schemas for meal logging and label parsing.
- Build a prototype reading surface before adding many agent flows.
- Build one complete agent flow: text meal log to confirmed diary entry.
