export const queryKeys = {
  people: (householdId: string | null) => ["people", householdId] as const,
  daySummary: (personId: string | null, day: string) => ["daySummary", personId, day] as const,
  activeGoal: (personId: string | null, day: string) => ["activeGoal", personId, day] as const,
  weightTrend: (personId: string | null) => ["weightTrend", personId] as const,
  weekSummary: (personId: string | null, start: string, end: string) => ["weekSummary", personId, start, end] as const,
  chatHistory: (personId: string | null) => ["chatHistory", personId] as const,
  proposals: (personId: string | null) => ["proposals", personId] as const,
  foods: (householdId: string | null, personId: string | null) => ["foods", householdId, personId] as const,
  rollingSummary: (personId: string | null, end: string) => ["rollingSummary", personId, end] as const,
  reviewNotes: (personId: string | null) => ["reviewNotes", personId] as const,
  jobs: (personId: string | null) => ["jobs", personId] as const,
};
