export type OutboxReason = "model_unavailable" | "network";

export type OutboxItem = {
  id: string;
  person_id: string;
  text: string;
  created_at: string;
  reason: OutboxReason;
};

const STORAGE_KEY = "health-monitor.outbox.v1";

export function enqueue(items: OutboxItem[], item: OutboxItem): OutboxItem[] {
  if (items.some((existing) => existing.id === item.id)) {
    return items;
  }
  return [...items, item];
}

export function removeById(items: OutboxItem[], id: string): OutboxItem[] {
  return items.filter((item) => item.id !== id);
}

export function forPerson(items: OutboxItem[], personId: string): OutboxItem[] {
  return items
    .filter((item) => item.person_id === personId)
    .sort((a, b) => a.created_at.localeCompare(b.created_at));
}

export function clearForPerson(items: OutboxItem[], personId: string): OutboxItem[] {
  return items.filter((item) => item.person_id !== personId);
}

export function readOutbox(storage: Pick<Storage, "getItem"> = localStorage): OutboxItem[] {
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as OutboxItem[]) : [];
  } catch {
    return [];
  }
}

export function writeOutbox(items: OutboxItem[], storage: Pick<Storage, "setItem"> = localStorage): void {
  storage.setItem(STORAGE_KEY, JSON.stringify(items));
}
