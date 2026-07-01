# Testing Strategy

Status: Draft
Created: 2026-07-01

## Goals

Tests should define app behavior before implementation details harden.

Priorities:

- Prefer behavior and contract tests over narrow implementation tests.
- Keep tests isolated and parallelizable.
- Keep deterministic calculations out of model calls.
- Test proposal-gated writes before building agent UI flows.
- Use real domain services in tests before mocking internals.

## Test Layers

### Behavior Tests

Behavior tests validate user-visible workflows across domain services.

Examples:

- Food version changes do not mutate historical diary entries.
- Barcode plus label scan creates a durable local association.
- Rejected agent proposal does not create diary entries.
- Confirmed proposal applies transactionally.
- Natural food aliases resolve through confirmed signals.

### Contract Tests

Contract tests validate boundaries.

Examples:

- NexusLog event shape.
- Agent proposal payload shape.
- Lookup candidate shape.
- API response schemas.

### Unit Tests

Unit tests cover deterministic calculations and small pure functions.

Examples:

- Nutrient scaling.
- Daily totals.
- Unit conversion.
- Target selection by date.

## Parallelization Rules

- Tests must not share mutable global state.
- Tests should use in-memory repositories unless explicitly marked otherwise.
- Database tests should use isolated schemas or transactions when added.
- Agent tests should assert structured output and tool usage, not exact prose.
- Network lookups should use recorded fixtures by default.

## Current Runner

The bootstrap suite uses stdlib `unittest` so it runs without installing dependencies:

```bash
make test
```

The project is configured so the suite can later run with pytest-xdist:

```bash
PYTHONPATH=src pytest -n auto
```

