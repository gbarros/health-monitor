# ChatGPT History Import Plan

Status: Draft
Created: 2026-07-01

## Purpose

Prior ChatGPT nutrition logs can help this project in two ways:

- Migration evidence: recover useful diary entries, foods, label facts, aliases, and reviews.
- Test evidence: derive realistic fixtures for agent behavior before implementation.

Raw exports can contain sensitive health data. They should stay local and should not be committed.

This is expected to be a one-off assisted migration path, not a polished end-user import feature in the MVP.

## Export Source

OpenAI documents two ways to request a copy of ChatGPT data:

- Privacy Portal: request a copy of account data.
- ChatGPT settings: profile menu, Settings, Data controls, Export data.

OpenAI notes that exports requested from ChatGPT settings are available for Free, Plus, Pro, and eligible Edu workspaces, but not for ChatGPT Business or Enterprise workspaces. Export delivery can take up to 7 days, and the download link expires 24 hours after it is received.

Official source: https://help.openai.com/en/articles/7260999-how-do-i-export-my-chatgpt-history-and-data

## Local Handling

Place raw exports under an ignored local folder, for example:

```text
imports/chatgpt/2026-07-export.zip
```

The repo ignores `imports/`, `data/imports/`, and `private/` so raw data is not committed accidentally.

## Supported Local Commands

Inspect a large exported HTML file without dumping private content:

```bash
python scripts/inspect_chatgpt_log.py <export.html>
```

Extract sanitized signal candidates to a local JSON file:

```bash
python scripts/extract_chatgpt_log_signals.py <export.html> --out <fixtures.json>
```

Optional date filters narrow candidates to blocks with inferred source context in the selected range:

```bash
python scripts/extract_chatgpt_log_signals.py <export.html> \
  --start-date 2026-07-01 \
  --end-date 2026-07-31 \
  --out <fixtures.json>
```

Use `--no-redact` only for local one-off work. Generated private snippets and raw exports should stay under ignored paths such as `private/`, `imports/`, or `data/imports/`.

## Import Strategy

The first parser should be conservative.

Inputs:

- ChatGPT export ZIP.
- Optional manually copied Canvas/log text if Canvas content is missing or incomplete in the export.
- Optional date range, such as the last 30 days.
- Optional conversation allowlist.

Outputs:

- Candidate diary entries.
- Candidate food records.
- Candidate food versions.
- Candidate aliases and phrase handles.
- Candidate review notes.
- Agent test fixtures.

The parser should not write durable app records directly. It should produce proposals or fixtures that can be inspected.

## Fixture Extraction Targets

Useful cases to extract:

- Repeated food references, such as "Iogurte Batavo" or "o leite mais proteico".
- Food label changes over time.
- Corrections made by the user after the assistant chose the wrong food.
- Meals logged with incomplete quantities.
- Social meals or restaurant meals that required external lookup.
- Weekly reviews and side quests.
- Micronutrient analysis requests.

## Privacy Rules

- Do not commit raw exports.
- Prefer generating sanitized fixtures before using real examples in tests.
- Preserve enough source context to understand why a fixture exists.
- Support redaction before fixture generation.
- Keep model-facing migration prompts scoped to selected conversations and date ranges.

## Open Questions

- Does the export include Canvas content in a useful form for this account?
- Should fixture generation preserve exact wording or use redacted paraphrases?
- Should imported diary entries remain proposals forever, or can confirmed imports become real records?
- What source references should be attached to imported records after confirmation?
