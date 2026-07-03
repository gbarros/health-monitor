/// <reference types="bun-types" />
import { describe, expect, test } from "bun:test";
import { clearForPerson, enqueue, forPerson, removeById } from "./outbox";
import type { OutboxItem } from "./outbox";

function item(overrides: Partial<OutboxItem> = {}): OutboxItem {
  return {
    id: "item-1",
    person_id: "person-1",
    text: "Almoço: 100g arroz",
    created_at: "2026-07-03T12:00:00.000Z",
    reason: "model_unavailable",
    ...overrides,
  };
}

describe("outbox", () => {
  test("enqueue appends a new item", () => {
    const result = enqueue([], item());
    expect(result).toEqual([item()]);
  });

  test("enqueue dedupes by id", () => {
    const existing = [item()];
    const result = enqueue(existing, item({ text: "different text, same id" }));
    expect(result).toEqual(existing);
  });

  test("removeById drops only the matching item", () => {
    const items = [item({ id: "a" }), item({ id: "b" })];
    expect(removeById(items, "a")).toEqual([item({ id: "b" })]);
  });

  test("forPerson filters to the given person and sorts oldest-first", () => {
    const items = [
      item({ id: "later", person_id: "person-1", created_at: "2026-07-03T12:00:00.000Z" }),
      item({ id: "other-person", person_id: "person-2", created_at: "2026-07-03T09:00:00.000Z" }),
      item({ id: "earlier", person_id: "person-1", created_at: "2026-07-03T08:00:00.000Z" }),
    ];
    expect(forPerson(items, "person-1").map((entry) => entry.id)).toEqual(["earlier", "later"]);
  });

  test("clearForPerson removes all items for a person and keeps others", () => {
    const items = [
      item({ id: "mine", person_id: "person-1" }),
      item({ id: "theirs", person_id: "person-2" }),
    ];
    expect(clearForPerson(items, "person-1").map((entry) => entry.id)).toEqual(["theirs"]);
  });
});
