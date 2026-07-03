export type Person = {
  id: string;
  household_id: string;
  name: string;
  timezone: string;
  birth_date?: string | null;
  sex?: string | null;
  height_cm?: number | null;
  activity_level?: string | null;
};

export type Household = {
  id: string;
  name: string;
};

export type Nutrients = {
  calories_kcal?: number;
  protein_g?: number;
  carbs_g?: number;
  fat_g?: number;
  fiber_g?: number;
  sodium_mg?: number;
};

export type GoalProfile = {
  id: string;
  person_id: string;
  starts_on: string;
  ends_on?: string | null;
  targets: Nutrients;
  notes?: string | null;
  created_at: string;
};

export type DaySummaryEntry = {
  id: string;
  logged_at: string;
  meal_type: string;
  food_id: string;
  food_name: string;
  brand?: string | null;
  food_version_id: string;
  food_version_label: string;
  quantity_g: number;
  nutrients: Nutrients;
  source: string;
  evidence_status: string;
  confidence: number;
};

export type DaySummary = {
  person_id: string;
  day: string;
  totals: Nutrients;
  target?: Nutrients | null;
  target_delta?: Nutrients | null;
  meals: Record<string, DaySummaryEntry[]>;
};

export type WeightEntry = {
  id: string;
  person_id: string;
  measured_at: string;
  weight_kg: number;
  note?: string | null;
  source: string;
};

export type WeightTrend = {
  person_id: string;
  entries: WeightEntry[];
  latest_kg?: number | null;
  delta_kg?: number | null;
};

export type Proposal = {
  id: string;
  person_id: string;
  proposal_type: string;
  status: string;
  summary: string;
  totals?: Nutrients;
  payload?: Record<string, unknown>;
  evidence?: Array<Record<string, unknown>>;
  entries?: ProposalEntry[];
  created_at?: string;
  confirmed_at?: string | null;
  rejected_at?: string | null;
};

export type ProposalEntry = {
  id: string;
  logged_at: string;
  meal_type: string;
  food_id?: string;
  food_name?: string;
  brand?: string | null;
  food_version_id: string;
  food_version_label?: string;
  quantity_g: number;
  nutrients?: Nutrients;
  source?: string;
  confidence?: number;
};

export type AgentChatResponse = {
  run_id: string;
  person_id: string;
  message: string;
  behavior_label: string;
  citations: Array<Record<string, string>>;
  proposal_id?: string | null;
  proposal?: Proposal | null;
};

export type AgentChatTurn = {
  id: string;
  person_id: string;
  agent_run_id: string;
  user_message: string;
  assistant_message: string;
  behavior_label: string;
  citations: Array<Record<string, string>>;
  proposal_id?: string | null;
  created_at: string;
};

export type AppEvent = {
  id: string;
  title: string;
  detail: string;
  tone: "info" | "success" | "warning" | "danger";
  createdAt: string;
};

export type AgentSettings = {
  agent_runtime: "deterministic" | "pydantic-ai";
  model_profile: string;
  effort: "low" | "normal" | "medium" | "high";
  max_tool_loops: number;
  research_lookup: boolean;
};

export type OnboardingDraft = {
  householdName: string;
  personName: string;
  timezone: string;
  activityLevel: string;
  targets: Required<Nutrients>;
};
