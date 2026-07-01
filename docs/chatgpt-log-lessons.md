# Lessons From ChatGPT Nutrition Log Export

Status: Draft
Created: 2026-07-01

## Source

Private source file:

```text
Health - Diario_ Nutricao e Perda de Peso.html
```

The raw file is intentionally ignored by git. The committed docs should capture product lessons, not private diary contents.

## Extraction Summary

The export is a large HTML rendering of the ChatGPT/Canvas experience, not a clean data file.

Observed structure:

- File size: about 33 MB.
- Extracted visible content blocks: 10,615.
- Paragraph blocks: 5,320.
- Table cells: 3,035.
- Table headers: 825.
- Headings: 983 across `h1` to `h4`.
- Tables in raw HTML: 194.

Signal counts from extracted blocks:

- Macro or calorie references: 3,118.
- Food alias candidates: 596.
- Weight or goal references: 254.
- Label or table references: 170.
- Uncertainty or approximation references: 165.
- Micronutrient references: 138.
- Review or pattern references: 126.
- Correction or revision references: 120.
- Date or day references: 117.
- Recipe or batch references: 51.
- Restaurant or external lookup references: 16.

These counts are not meant to be exact nutrition analytics. They are product-design signals.

## Product Lessons

### L-001: The App Needs Both Logging And Coaching

The old workflow was not only a diary. It mixed logging, interpretation, coaching, adjustment, and review.

Implication:

- Diary entries, review notes, and agent explanations should be separate record types.
- The app should support "what should I adjust?" without turning that answer into diary data.
- Weekly reviews and side quests should be first-class outputs.

Related behavior:

- `F-009: Free Agent Chat`
- `F-011: Macro And Trend Review`
- `F-012: Micronutrient Side Quests`

### L-002: Table And Macro Parsing Are Core, Not Peripheral

The export is table-heavy and macro-heavy. The current process relied on structured daily summaries, not only prose.

Implication:

- The parser must handle table-like text and HTML tables.
- The app should represent calories, protein, carbohydrate, fat, fiber, sodium, and other nutrients as structured fields.
- Deterministic recalculation matters because the old workflow repeatedly revisited totals.

Related behavior:

- `CR-003: Calculations Are Deterministic`
- `F-007: Nutrition Label Or Table Scan`

### L-003: Natural Food References Are A First-Class Problem

Food mentions are not stable database names. They are natural phrases, brand references, nicknames, and recent-context references.

Implication:

- `FoodAlias` and `FoodResolutionSignal` are required early.
- The app should support phrases such as "the more protein milk", "the new cheese", and "the yogurt from this week".
- Corrections should improve future food resolution.

Related behavior:

- `CR-008: User Food Names Are Not Version IDs`
- `F-016: Food Reference Resolution`

### L-004: Approximation Is A Normal State

The old workflow often used ranges and estimates. This is expected for restaurants, unlabeled foods, and ambiguous serving sizes.

Implication:

- The app should store confidence and evidence status.
- The UI should show exact, inferred, looked up, and estimated states.
- The agent should be allowed to produce useful estimates, but they should not be presented as precise labels.

Related behavior:

- `CR-006: Uncertainty Is Visible`
- `F-003: External Food Lookup`
- `F-018: Controlled Research-Agent Lookup`

### L-005: Corrections Are A Daily-Driver Workflow

Corrections and adjustments appear frequently enough to deserve product support.

Implication:

- "Correct previous entry" should be easy from chat and the diary UI.
- Corrections should produce proposals.
- The app should preserve why a correction happened.

Related behavior:

- `CR-002: Agent Writes Go Through Proposals`
- `F-009: Free Agent Chat`
- `Proposal Contract`

### L-006: Restaurant And Social Meals Need A Different Confidence Model

Restaurant or social meals are less frequent than normal macro logging, but they are high-impact and less precise.

Implication:

- Controlled research-agent lookup is useful as a fallback source adapter.
- Restaurant meals should support range estimates and evidence notes.
- The app should preserve whether a source is official, third-party, or model-inferred.

Related behavior:

- `F-003: External Food Lookup`
- `F-018: Controlled Research-Agent Lookup`

### L-007: Recipes And Batch Foods Should Be Versioned

Recipe and batch-food references appear in the export. Prepared foods need yield-aware calculation.

Implication:

- Recipe versions should store ingredient versions and yield.
- Missing yield should create a draft recipe, not a precise loggable food.
- Logged recipe portions should remain tied to the version active at the time.

Related behavior:

- `F-008: Recipe And Batch Food Registration`

### L-008: Weight And Goals Are Interwoven With The Diary

The old workflow mixed nutrition logs with weight trend and target discussion.

Implication:

- Weight entries and goal profiles should be dated structured records.
- Reviews should be able to combine diary summaries with weight trend.
- Changing goals should not rewrite past comparisons.

Related behavior:

- `F-001: Household And Person Profile`
- `F-010: Weight Log`
- `F-011: Macro And Trend Review`

### L-009: Micronutrients Are Side Quests, But They Matter

Micronutrient references are less frequent than macro references, but they appear enough to justify a later analysis surface.

Implication:

- The schema should support micronutrients from day one.
- The MVP UI can emphasize macros, but data model and imports should not discard micronutrients.
- Side-quest analysis should distinguish tracked nutrients from inferred dietary patterns.

Related behavior:

- `F-012: Micronutrient Side Quests`

### L-010: Portuguese And Mixed Natural Language Are Expected

The log contains Portuguese food and nutrition language.

Implication:

- Aliases and parsing should support Portuguese phrases.
- Food lookup should handle local Brazilian product names and restaurant context.
- Tests should include Portuguese examples.

Related behavior:

- `F-016: Food Reference Resolution`
- `F-003: External Food Lookup`

## Fixture Ideas From The Export

Use the export to create sanitized fixtures before implementation.

Priority fixture themes:

- Exact meal with grams and macros.
- Vague meal with common household foods.
- Repeated food alias resolved by recency.
- New product label superseding older default.
- Restaurant meal estimated by range.
- Correction to a previous diary entry.
- Recipe or batch food with explicit yield.
- Recipe or batch food missing yield.
- Day closeout with calories/macros and notes.
- Weekly review connecting macros, consistency, and weight trend.
- Micronutrient side-quest with limited evidence.

## Import Parser Requirements

The raw HTML should not be parsed as plain text only.

Minimum parser behavior:

- Extract visible blocks from headings, paragraphs, list items, table headers, and table cells.
- Preserve source block order.
- Detect date/day headings.
- Detect macro tables and daily summaries.
- Detect likely diary entries, review notes, food aliases, recipes, and corrections.
- Generate proposals or fixtures, not direct records.
- Preserve source references for audit.

## Tooling Added

Current local scripts:

- `scripts/inspect_chatgpt_log.py`: reports HTML structure and keyword counts without dumping content.
- `scripts/extract_chatgpt_log_signals.py`: classifies extracted blocks into product-signal categories and can write private local snippets.

Private generated files should stay under:

```text
private/
imports/
data/imports/
```
