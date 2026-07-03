import type {
  AgentChatResponse,
  AgentChatTurn,
  AgentSettings,
  Attachment,
  BackgroundJob,
  DaySummary,
  Food,
  FoodLookupCandidate,
  FoodResponse,
  GoalProfile,
  Household,
  OnboardingDraft,
  Person,
  Proposal,
  ReviewNote,
  RollingSummary,
  WeightTrend,
  WeekSummary,
} from "./types";

export const STORAGE_KEYS = {
  householdId: "health-monitor.household-id",
  personId: "health-monitor.person-id",
  selectedDay: "health-monitor.selected-day",
} as const;

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(path);
  return decodeResponse<T>(response);
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return decodeResponse<T>(response);
}

export class ApiError extends Error {
  readonly type: string;
  readonly replayMessage: string | null;

  constructor(message: string, type: string, replayMessage: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.type = type;
    this.replayMessage = replayMessage;
  }
}

async function decodeResponse<T>(response: Response): Promise<T> {
  const payload = (await response.json().catch(() => ({}))) as
    | T
    | { error?: { type?: string; message?: string; replay_message?: string | null } };
  if (!response.ok) {
    const error =
      typeof payload === "object" && payload !== null && "error" in payload
        ? payload.error
        : undefined;
    throw new ApiError(
      error?.message ?? `HTTP ${response.status}`,
      error?.type ?? `http_${response.status}`,
      error?.replay_message ?? null,
    );
  }
  return payload as T;
}

export async function createInitialProfile(draft: OnboardingDraft): Promise<{
  household: Household;
  person: Person;
}> {
  const household = await apiPost<Household>("/api/households", { name: draft.householdName });
  const person = await apiPost<Person>("/api/people", {
    household_id: household.id,
    name: draft.personName,
    timezone: draft.timezone,
    activity_level: draft.activityLevel,
  });
  await apiPost("/api/goals", {
    person_id: person.id,
    starts_on: todayIsoForTimezone(draft.timezone),
    targets: draft.targets,
    notes: "Created from chat-first onboarding.",
  });
  localStorage.setItem(STORAGE_KEYS.householdId, household.id);
  localStorage.setItem(STORAGE_KEYS.personId, person.id);
  return { household, person };
}

export async function loadPeople(householdId: string): Promise<Person[]> {
  return apiGet<Person[]>(`/api/people?household_id=${encodeURIComponent(householdId)}`);
}

export async function loadChatHistory(personId: string): Promise<AgentChatTurn[]> {
  return apiGet<AgentChatTurn[]>(`/api/agent/chat-history?person_id=${encodeURIComponent(personId)}`);
}

export async function loadDaySummary(personId: string, day: string): Promise<DaySummary> {
  return apiGet<DaySummary>(
    `/api/diary/day?person_id=${encodeURIComponent(personId)}&day=${encodeURIComponent(day)}`,
  );
}

export async function loadActiveGoal(personId: string, day: string): Promise<GoalProfile | null> {
  const goal = await apiGet<Partial<GoalProfile>>(
    `/api/goals/active?person_id=${encodeURIComponent(personId)}&day=${encodeURIComponent(day)}`,
  );
  return typeof goal.id === "string" ? (goal as GoalProfile) : null;
}

export async function loadWeightTrend(personId: string): Promise<WeightTrend> {
  return apiGet<WeightTrend>(`/api/weights/trend?person_id=${encodeURIComponent(personId)}`);
}

export async function loadWeekSummary(personId: string, start: string, end: string): Promise<WeekSummary> {
  return apiGet<WeekSummary>(
    `/api/summaries/week?person_id=${encodeURIComponent(personId)}&start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`,
  );
}

export async function loadProposals(personId: string): Promise<Proposal[]> {
  return apiGet<Proposal[]>(`/api/proposals?person_id=${encodeURIComponent(personId)}`);
}

export async function confirmProposal(proposalId: string): Promise<Proposal> {
  return apiPost<Proposal>(`/api/proposals/${encodeURIComponent(proposalId)}/confirm`, {});
}

export async function rejectProposal(proposalId: string): Promise<Proposal> {
  return apiPost<Proposal>(`/api/proposals/${encodeURIComponent(proposalId)}/reject`, {});
}

export async function loadProposal(proposalId: string): Promise<Proposal> {
  return apiGet<Proposal>(`/api/proposals/${encodeURIComponent(proposalId)}`);
}

export async function resolveProposalClarification(input: {
  proposalId: string;
  unresolvedIndex: number;
  foodVersionId: string;
}): Promise<Proposal> {
  return apiPost<Proposal>(`/api/proposals/${encodeURIComponent(input.proposalId)}/resolve-food`, {
    unresolved_index: input.unresolvedIndex,
    food_version_id: input.foodVersionId,
  });
}

export async function updateProposalEntry(input: {
  proposalId: string;
  entryId: string;
  quantityG?: number;
  mealType?: string;
  foodVersionId?: string;
}): Promise<Proposal> {
  const response = await fetch(
    `/api/proposals/${encodeURIComponent(input.proposalId)}/entries/${encodeURIComponent(input.entryId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        quantity_g: input.quantityG,
        meal_type: input.mealType,
        food_version_id: input.foodVersionId,
      }),
    },
  );
  return decodeResponse<Proposal>(response);
}

export async function logWeight(input: {
  personId: string;
  weightKg: number;
  measuredAtLocal?: string;
  note?: string;
}): Promise<unknown> {
  return apiPost("/api/weights", {
    person_id: input.personId,
    measured_at_local: input.measuredAtLocal ?? localDateTimeForApi(),
    weight_kg: input.weightKg,
    note: input.note,
    source: "manual_ui",
  });
}

export async function updateDiaryEntry(input: {
  entryId: string;
  quantityG?: number;
  mealType?: string;
  loggedAtLocal?: string;
}): Promise<{ id: string }> {
  const response = await fetch(`/api/diary/${encodeURIComponent(input.entryId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      quantity_g: input.quantityG,
      meal_type: input.mealType,
      logged_at_local: input.loggedAtLocal,
    }),
  });
  return decodeResponse<{ id: string }>(response);
}

export async function deleteDiaryEntry(entryId: string): Promise<{ id: string }> {
  const response = await fetch(`/api/diary/${encodeURIComponent(entryId)}`, { method: "DELETE" });
  return decodeResponse<{ id: string }>(response);
}

export async function restoreDiaryEntry(entryId: string): Promise<{ id: string }> {
  return apiPost<{ id: string }>(`/api/diary/${encodeURIComponent(entryId)}/restore`, {});
}

export async function enqueueAgentChatJob(input: {
  personId: string;
  message: string;
  settings: AgentSettings;
  today?: string;
  attachmentIds?: string[];
}): Promise<BackgroundJob> {
  return apiPost<BackgroundJob>("/api/jobs", {
    job_type: "agent_chat",
    payload: {
      person_id: input.personId,
      message: input.message,
      today: input.today ?? todayIso(),
      agent_settings: input.settings,
      attachment_ids: input.attachmentIds?.length ? input.attachmentIds : undefined,
    },
  });
}

export async function loadJobs(personId: string): Promise<BackgroundJob[]> {
  return apiGet<BackgroundJob[]>(`/api/jobs?person_id=${encodeURIComponent(personId)}`);
}

export async function processJob(jobId: string): Promise<BackgroundJob> {
  return apiPost<BackgroundJob>(`/api/jobs/${encodeURIComponent(jobId)}/process`, {});
}

export async function loadRollingSummary(input: {
  personId: string;
  end: string;
  days?: number;
}): Promise<RollingSummary> {
  return apiGet<RollingSummary>(
    `/api/summaries/rolling?person_id=${encodeURIComponent(input.personId)}&end=${encodeURIComponent(input.end)}&days=${input.days ?? 7}`,
  );
}

export async function loadReviewNotes(personId: string): Promise<ReviewNote[]> {
  return apiGet<ReviewNote[]>(`/api/review-notes?person_id=${encodeURIComponent(personId)}`);
}

export async function exportFullData(): Promise<unknown> {
  return apiGet<unknown>("/api/exports/full");
}

export async function importFullData(data: unknown): Promise<{ imported: unknown }> {
  return apiPost<{ imported: unknown }>("/api/imports/full", data);
}

export async function loadFoods(input: { householdId: string; personId?: string }): Promise<FoodResponse[]> {
  const params = new URLSearchParams({ household_id: input.householdId });
  if (input.personId) {
    params.set("person_id", input.personId);
  }
  return apiGet<FoodResponse[]>(`/api/foods?${params.toString()}`);
}

export async function archiveFood(foodId: string): Promise<Food> {
  return apiPost<Food>(`/api/foods/${encodeURIComponent(foodId)}/archive`, {});
}

export async function loadLookupCandidates(input: {
  householdId: string;
  personId: string;
  phrase?: string;
  barcode?: string;
}): Promise<FoodLookupCandidate[]> {
  const params = new URLSearchParams({ household_id: input.householdId, person_id: input.personId });
  if (input.phrase) {
    params.set("phrase", input.phrase);
  }
  if (input.barcode) {
    params.set("barcode", input.barcode);
  }
  return apiGet<FoodLookupCandidate[]>(`/api/lookups/foods?${params.toString()}`);
}

export async function proposeLookupCandidate(input: {
  householdId: string;
  personId: string;
  candidateId: string;
}): Promise<Proposal> {
  return apiPost<Proposal>("/api/lookups/foods/propose", {
    household_id: input.householdId,
    person_id: input.personId,
    candidate_id: input.candidateId,
  });
}

export async function loadAttachment(attachmentId: string): Promise<Attachment> {
  return apiGet<Attachment>(`/api/attachments/${encodeURIComponent(attachmentId)}`);
}

export async function logCustomFood(input: {
  householdId: string;
  personId: string;
  name: string;
  brand?: string;
  versionLabel: string;
  nutrientsPer100g: {
    calories_kcal: number;
    protein_g: number;
    carbs_g: number;
    fat_g: number;
    fiber_g?: number;
    sodium_mg?: number;
  };
  quantityG: number;
  mealType?: string;
  loggedAtLocal?: string;
}): Promise<unknown> {
  return apiPost("/api/diary/custom-food", {
    household_id: input.householdId,
    person_id: input.personId,
    name: input.name,
    brand: input.brand,
    version_label: input.versionLabel,
    nutrients_per_100g: input.nutrientsPer100g,
    logged_at_local: input.loggedAtLocal ?? localDateTimeForApi(),
    quantity_g: input.quantityG,
    meal_type: input.mealType,
  });
}

export async function logFoodVersion(input: {
  personId: string;
  foodVersionId: string;
  quantityG: number;
  mealType?: string;
  loggedAtLocal?: string;
}): Promise<unknown> {
  return apiPost("/api/diary", {
    person_id: input.personId,
    logged_at_local: input.loggedAtLocal ?? localDateTimeForApi(),
    food_version_id: input.foodVersionId,
    quantity_g: input.quantityG,
    source: "manual_ui",
    meal_type: input.mealType,
  });
}

export async function updateWeightEntry(input: {
  entryId: string;
  weightKg?: number;
  measuredAtLocal?: string;
  note?: string;
}): Promise<unknown> {
  const response = await fetch(`/api/weights/${encodeURIComponent(input.entryId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      weight_kg: input.weightKg,
      measured_at_local: input.measuredAtLocal,
      note: input.note,
    }),
  });
  return decodeResponse(response);
}

export async function repeatMeal(input: {
  personId: string;
  sourceDay: string;
  mealType: string;
  loggedAtLocal?: string;
}): Promise<Proposal> {
  return apiPost<Proposal>("/api/diary/repeat", {
    person_id: input.personId,
    source_day: input.sourceDay,
    meal_type: input.mealType,
    logged_at_local: input.loggedAtLocal ?? localDateTimeForApi(),
  });
}

export async function sendAgentChat(input: {
  personId: string;
  message: string;
  settings: AgentSettings;
  today?: string;
  attachmentIds?: string[];
  signal?: AbortSignal;
}): Promise<AgentChatResponse> {
  const response = await fetch("/api/agent/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      person_id: input.personId,
      message: input.message,
      today: input.today ?? todayIso(),
      agent_settings: input.settings,
      attachment_ids: input.attachmentIds?.length ? input.attachmentIds : undefined,
    }),
    signal: input.signal,
  });
  return decodeResponse<AgentChatResponse>(response);
}

export async function draftTextMeal(input: {
  personId: string;
  text: string;
  settings: AgentSettings;
  amendProposalId?: string;
  signal?: AbortSignal;
}): Promise<Proposal> {
  const response = await fetch("/api/agent/text-meal", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      person_id: input.personId,
      logged_at_local: localDateTimeForApi(),
      text: input.text,
      agent_settings: input.settings,
      amend_proposal_id: input.amendProposalId,
    }),
    signal: input.signal,
  });
  return decodeResponse<Proposal>(response);
}

export async function draftRecipe(input: {
  householdId: string;
  personId: string;
  text: string;
  quantityG?: number;
  signal?: AbortSignal;
}): Promise<Proposal> {
  const response = await fetch("/api/agent/recipe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      household_id: input.householdId,
      person_id: input.personId,
      recipe_text: input.text,
      logged_at_local: input.quantityG != null ? localDateTimeForApi() : undefined,
      quantity_g: input.quantityG,
    }),
    signal: input.signal,
  });
  return decodeResponse<Proposal>(response);
}

export async function draftLabelScan(input: {
  householdId: string;
  personId: string;
  text: string;
  attachmentIds: string[];
  signal?: AbortSignal;
}): Promise<Proposal> {
  const response = await fetch("/api/agent/label-scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      household_id: input.householdId,
      person_id: input.personId,
      table_text: input.text || undefined,
      barcode: extractBarcode(input.text) ?? undefined,
      attachment_ids: input.attachmentIds.length ? input.attachmentIds : undefined,
      set_as_default: true,
    }),
    signal: input.signal,
  });
  return decodeResponse<Proposal>(response);
}

export async function uploadDataUrlAttachment(input: {
  householdId: string;
  personId: string;
  dataUrl: string;
  filename?: string;
  objectType?: string;
}): Promise<{ id: string }> {
  const parsed = parseDataUrl(input.dataUrl);
  return apiPost<{ id: string }>("/api/attachments", {
    household_id: input.householdId,
    person_id: input.personId,
    object_type: input.objectType ?? "nutrition_label",
    mime_type: parsed.mimeType,
    filename: input.filename,
    content_base64: parsed.contentBase64,
    retention_policy: "keep",
  });
}

export function parseOnboardingMessage(message: string): OnboardingDraft {
  const text = message.trim();
  const naturalName = extractNaturalName(text);
  const naturalTimezone = extractNaturalTimezone(text);
  const naturalActivity = extractNaturalActivity(text);
  return {
    householdName: extractText(text, ["household", "casa", "family"], "Casa"),
    personName: extractText(text, ["name", "nome", "person"], naturalName ?? "Gabriel"),
    timezone: extractText(text, ["timezone", "fuso"], naturalTimezone ?? guessTimezone()),
    activityLevel: extractText(text, ["activity", "atividade"], naturalActivity ?? "moderate"),
    targets: {
      calories_kcal: extractNumber(text, ["calories", "calorias", "kcal"], 2000),
      protein_g: extractNumber(text, ["protein", "proteina", "proteína"], 150),
      carbs_g: extractNumber(text, ["carbs", "carbo", "carboidratos"], 180),
      fat_g: extractNumber(text, ["fat", "gordura"], 70),
      fiber_g: extractNumber(text, ["fiber", "fibra"], 30),
      sodium_mg: extractNumber(text, ["sodium", "sodio", "sódio"], 2300),
    },
  };
}

export function defaultAgentSettings(): AgentSettings {
  return {
    agent_runtime: "pydantic-ai",
    model_profile: "qwen3.6:latest",
    effort: "medium",
    max_tool_loops: 6,
    research_lookup: true,
  };
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function todayIsoForTimezone(timezone: string | null | undefined): string {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone || guessTimezone(),
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  return formatter.format(new Date());
}

function localDateTimeForApi(): string {
  const now = new Date();
  const date = now.toISOString().slice(0, 10);
  const time = now.toTimeString().slice(0, 8);
  return `${date}T${time}`;
}

function guessTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "America/Sao_Paulo";
}

function extractText(text: string, labels: string[], fallback: string): string {
  for (const label of labels) {
    const match = text.match(new RegExp(`(?:^|\\n)\\s*${label}\\s*[:=-]\\s*([^\\n]+)`, "i"));
    if (match?.[1]?.trim()) {
      return match[1].trim();
    }
  }
  return fallback;
}

function extractNumber(text: string, labels: string[], fallback: number): number {
  for (const label of labels) {
    const beforeLabel = text.match(new RegExp(`(\\d+(?:[.,]\\d+)?)\\s*(?:g|mg|kcal)?\\s+${label}`, "i"));
    if (beforeLabel?.[1]) {
      return Number(beforeLabel[1].replace(",", "."));
    }
    const afterLabel = text.match(new RegExp(`${label}[^\\d]*(\\d+(?:[.,]\\d+)?)`, "i"));
    if (afterLabel?.[1]) {
      return Number(afterLabel[1].replace(",", "."));
    }
  }
  return fallback;
}

function extractNaturalName(text: string): string | null {
  const match =
    text.match(/\b(?:meu nome é|me chamo|sou|i am|my name is)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ '-]{1,40})/i) ??
    text.match(/\b(?:para|for)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ '-]{1,40})\b/i);
  if (!match?.[1]) {
    return null;
  }
  return match[1].replace(/\s+(?:e|and)\b.*$/i, "").trim();
}

function extractNaturalTimezone(text: string): string | null {
  const match = text.match(/\b(?:America|Europe|Asia|Africa|Pacific|Atlantic|Australia)\/[A-Za-z_/-]+\b/);
  return match?.[0] ?? null;
}

function extractNaturalActivity(text: string): string | null {
  const match = text.match(/\b(?:atividade|activity)\s+(?:é|is)?\s*(sedent[aá]ria|sedentary|leve|light|moderada|moderate|alta|high)\b/i);
  if (!match?.[1]) {
    return null;
  }
  const value = match[1].toLocaleLowerCase("pt-BR");
  if (value.startsWith("sedent")) return "sedentary";
  if (value === "leve" || value === "light") return "light";
  if (value === "moderada" || value === "moderate") return "moderate";
  if (value === "alta" || value === "high") return "high";
  return value;
}

function extractBarcode(text: string): string | null {
  const match = text.match(/\b\d{8,14}\b/);
  return match?.[0] ?? null;
}

function parseDataUrl(dataUrl: string): { mimeType: string; contentBase64: string } {
  const match = dataUrl.match(/^data:([^;]+);base64,(.*)$/);
  if (!match) {
    throw new Error("Unsupported attachment encoding");
  }
  return {
    mimeType: match[1],
    contentBase64: match[2],
  };
}
