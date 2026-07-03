export type ModeId =
  | "general_chat"
  | "text_meal"
  | "label_scan"
  | "recipe"
  | "correction"
  | "review_note";

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

export type Proposal = {
  id: string;
  person_id: string;
  proposal_type: string;
  status: string;
  summary: string;
  totals?: Nutrients;
  payload?: Record<string, unknown>;
  evidence?: Array<Record<string, unknown>>;
  entries?: Array<Record<string, unknown>>;
  created_at?: string;
  confirmed_at?: string | null;
  rejected_at?: string | null;
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
