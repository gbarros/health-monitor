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

export type WeekSummary = {
  person_id: string;
  start: string;
  end: string;
  daily: Record<string, Nutrients>;
  daily_targets: Record<string, Nutrients>;
  totals: Nutrients;
  averages: Nutrients;
  weight_delta_kg?: number | null;
};

export type AgentToolCall = {
  id: string;
  agent_run_id: string;
  tool_name: string;
  input_summary?: string | null;
  output_summary?: string | null;
  status: string;
  error?: string | null;
  started_at: string;
  completed_at?: string | null;
};

export type AgentRun = {
  id: string;
  person_id: string;
  input_text?: string | null;
  status: string;
  proposal_id?: string | null;
  runtime?: string | null;
  model_name?: string | null;
  tool_loop_count?: number;
  fallback_reason?: string | null;
  created_at: string;
  tool_calls: AgentToolCall[];
};

export type ProposalCandidate = {
  food_id: string;
  food_version_id: string;
  food_name: string;
  brand?: string | null;
  version_label: string;
  nutrients_per_100g?: Nutrients;
  confidence?: number;
  reason?: string;
};

export type UnresolvedItem = {
  source_text?: string;
  phrase?: string;
  unit?: string | null;
  quantity?: number;
  quantity_basis?: string | null;
  candidates?: ProposalCandidate[];
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
  agent_run?: AgentRun | null;
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

export type Food = {
  id: string;
  household_id: string;
  name: string;
  brand?: string | null;
  default_version_id?: string | null;
  archived: boolean;
};

export type FoodVersionSummary = {
  id: string;
  food_id: string;
  label: string;
  nutrients_per_100g: Nutrients;
  source: string;
  serving_size_g?: number | null;
  confidence: number;
  created_at: string;
  archived: boolean;
};

export type Attachment = {
  id: string;
  household_id: string;
  object_type: string;
  mime_type: string;
  filename?: string | null;
  created_at: string;
  content_base64?: string;
};

export type FoodResponse = {
  food: Food;
  version: FoodVersionSummary;
  aliases: string[];
  barcodes: string[];
  is_default: boolean;
  last_used_at?: string | null;
  attachments: Attachment[];
};

export type FoodLookupCandidate = {
  id: string;
  source_type: string;
  source_name?: string | null;
  source_id?: string | null;
  source_url?: string | null;
  product_name?: string | null;
  brand?: string | null;
  barcode?: string | null;
  food_id?: string | null;
  food_version_id?: string | null;
  serving_size_g?: number | null;
  nutrients_per_100g: Nutrients;
  confidence: number;
  warnings: string[];
};

export type OnboardingDraft = {
  householdName: string;
  personName: string;
  timezone: string;
  activityLevel: string;
  targets: Required<Nutrients>;
};
