import {
  defineAgentChatElement,
  type AgentChatAttachment,
  type AgentChatDraftCard,
  type AgentChatElement,
  type AgentChatElementState,
  type AgentChatMessage,
  type AgentChatMode,
  type AgentChatSendPayload,
  type AgentChatStatus
} from "@health-monitor/agent-chat-ui";
import "@health-monitor/agent-chat-ui/styles.css";
import "./styles.css";

defineAgentChatElement();

type Nutrients = {
  calories_kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  sodium_mg: number;
};

type Household = { id: string; name: string };
type Person = {
  id: string;
  household_id: string;
  name: string;
  timezone: string;
  birth_date: string | null;
  sex: string | null;
  height_cm: number | null;
  activity_level: string | null;
};
type GoalProfile = {
  id: string;
  person_id: string;
  starts_on: string;
  ends_on: string | null;
  targets: Nutrients;
  notes: string | null;
};
type FoodVersion = {
  id: string;
  food_id: string;
  label: string;
  nutrients_per_100g: Nutrients;
  serving_size_g: number | null;
  source?: string;
  confidence?: number;
};
type Food = { id: string; name: string; brand: string | null; default_version_id: string; archived?: boolean };
type FoodResponse = {
  food: Food;
  version: FoodVersion;
  aliases: string[];
  barcodes: string[];
  is_default: boolean;
  last_used_at: string | null;
  attachments: AttachmentObject[];
};
type QuickCustomFoodResponse = FoodResponse & { entry: DiaryEntryRecord };
type FoodLookupCandidate = {
  id: string;
  source_type: string;
  source_name: string;
  source_id: string;
  source_url: string | null;
  product_name: string;
  brand: string | null;
  barcode: string | null;
  food_id: string | null;
  food_version_id: string | null;
  serving_size_g: number | null;
  nutrients_per_100g: Nutrients;
  confidence: number;
  warnings: string[];
};
type AttachmentObject = {
  id: string;
  object_type: string;
  mime_type: string;
  byte_size: number;
  sha256: string;
  filename: string | null;
  linked_record_type: string | null;
  linked_record_id: string | null;
};
type SummaryEntry = {
  id: string;
  logged_at: string;
  meal_type: string;
  food_id: string;
  food_version_id: string;
  food_name: string;
  brand: string | null;
  food_version_label: string;
  quantity_g: number;
  nutrients: Nutrients;
  source: string;
  evidence_status: string;
  confidence: number;
};
type DiaryEntryRecord = {
  id: string;
  person_id: string;
  logged_at: string;
  meal_type: string;
  food_version_id: string;
  quantity_g: number;
  source: string;
  deleted_at: string | null;
};
type DaySummary = {
  person_id: string;
  day: string;
  totals: Nutrients;
  target: Nutrients | null;
  target_delta: Nutrients | null;
  meals: Record<string, SummaryEntry[]>;
};
type WeightEntry = {
  id: string;
  measured_at: string;
  weight_kg: number;
  note: string | null;
  source: string;
};
type WeightTrend = {
  person_id: string;
  entries: WeightEntry[];
  latest_kg: number | null;
  delta_kg: number | null;
};
type WeekSummary = {
  person_id: string;
  start: string;
  end: string;
  daily: Record<string, Nutrients>;
  daily_targets: Record<string, Nutrients>;
  totals: Nutrients;
  averages: Nutrients;
  weight_delta_kg: number | null;
};
type ReviewNote = {
  id: string;
  person_id: string;
  note_type: string;
  title: string;
  body: string;
  starts_on: string | null;
  ends_on: string | null;
  source: string;
  source_agent_run_id: string | null;
  source_proposal_id: string | null;
  created_at: string;
};
type ProposalEntry = SummaryEntry & { food_version_id: string };
type AgentToolCall = {
  id: string;
  agent_run_id: string;
  person_id: string;
  tool_name: string;
  input_summary: string;
  output_summary: string;
  status: string;
  source_record_ids: string[];
  error: string | null;
  started_at: string;
  completed_at: string | null;
};
type Proposal = {
  id: string;
  person_id: string;
  proposal_type: string;
  status: string;
  summary: string;
  payload: Record<string, unknown>;
  totals: Nutrients;
  evidence: Array<Record<string, string | number | boolean | null>>;
  applied_record_ids: string[];
  created_at: string;
  confirmed_at: string | null;
  rejected_at: string | null;
  agent_run: {
    id: string;
    settings: Record<string, string | number | boolean>;
    status: string;
    runtime: string | null;
    model_name: string | null;
    tool_loop_count: number;
    fallback_reason: string | null;
    tool_calls: AgentToolCall[];
  } | null;
  entries: ProposalEntry[];
};
type AgentChatResponse = {
  run_id: string;
  person_id: string;
  message: string;
  behavior_label: string;
  citations: Array<Record<string, string>>;
  proposal_id: string | null;
  proposal: Proposal | null;
};
type AgentChatTurn = {
  id: string;
  person_id: string;
  agent_run_id: string;
  user_message: string;
  assistant_message: string;
  behavior_label: string;
  citations: Array<Record<string, string>>;
  proposal_id: string | null;
  created_at: string;
};
type BackgroundJob = {
  id: string;
  job_type: string;
  status: string;
  payload: Record<string, unknown>;
  client_request_id: string | null;
  result: Record<string, unknown>;
  last_error: string | null;
  attempts: number;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
};
type OfflineOutboxKind = "agent_text_meal" | "agent_chat" | "agent_label_scan" | "agent_recipe";
type OfflineOutboxStatus = "pending" | "replaying" | "failed" | "sent";
type OfflineOutboxFile = {
  field: string;
  object_type: string;
  filename: string | null;
  mime_type: string;
  blob: Blob;
};
type BrowserBarcodeDetector = {
  detect(source: HTMLVideoElement): Promise<Array<{ rawValue?: string }>>;
};
type OfflineOutboxItem = {
  id: string;
  client_request_id: string;
  kind: OfflineOutboxKind;
  household_id: string | null;
  person_id: string;
  selected_day: string;
  payload: Record<string, unknown>;
  files: OfflineOutboxFile[];
  status: OfflineOutboxStatus;
  attempts: number;
  last_error: string | null;
  created_at: string;
  replayed_at: string | null;
};

type AppState = {
  household: Household | null;
  people: Person[];
  person: Person | null;
  selectedDay: string;
  activeGoal: GoalProfile | null;
  foods: FoodResponse[];
  foodFilter: string;
  lookupCandidates: FoodLookupCandidate[];
  summary: DaySummary | null;
  week: WeekSummary | null;
  weightTrend: WeightTrend | null;
  reviewNotes: ReviewNote[];
  proposal: Proposal | null;
  proposalQueue: Proposal[];
  chatResponse: AgentChatResponse | null;
  chatHistory: AgentChatTurn[];
  logMode: LogMode;
  logEvents: LogEvent[];
  jobs: BackgroundJob[];
  offlineOutbox: OfflineOutboxItem[];
  isOfflineReplayRunning: boolean;
  lastDeletedEntry: DiaryEntryRecord | null;
  exportText: string;
  notice: string | null;
  errorMessage: string | null;
};
type AppPage = "log" | "diary" | "review" | "library" | "work" | "settings";
type LogMode = "meal" | "label" | "recipe" | "chat" | "correction" | "review_note";
type LogEvent = {
  id: string;
  mode: LogMode;
  title: string;
  message: string;
  result: string;
  created_at: string;
};

const sessionStorageKey = "health-monitor.session.v1";
const outboxDbName = "health-monitor-offline-v1";
const outboxStoreName = "offline_outbox";
const state: AppState = {
  household: null,
  people: [],
  person: null,
  selectedDay: localDateInputValue(new Date()),
  activeGoal: null,
  foods: [],
  foodFilter: "",
  lookupCandidates: [],
  summary: null,
  week: null,
  weightTrend: null,
  reviewNotes: [],
  proposal: null,
  proposalQueue: [],
  chatResponse: null,
  chatHistory: [],
  logMode: "chat",
  logEvents: [],
  jobs: [],
  offlineOutbox: [],
  isOfflineReplayRunning: false,
  lastDeletedEntry: null,
  exportText: "",
  notice: null,
  errorMessage: null
};

const appRoot = requireAppRoot();
let jobPollTimer: number | null = null;
let barcodeScannerStream: MediaStream | null = null;
let barcodeScannerTimer: number | null = null;

render();
void loadOfflineOutbox();
void hydrateStoredSession();
registerServiceWorker();
window.addEventListener("online", () => {
  state.notice = "Connection restored. Replaying offline notes.";
  render();
  void replayOfflineOutbox();
});
window.addEventListener("offline", () => {
  state.notice = "Offline mode: agent notes and uploads will be saved locally.";
  render();
});
window.addEventListener("hashchange", () => render());

function render(): void {
  const needsSetup = !state.household || !state.person;
  const activePage = resolveActivePage(needsSetup);
  appRoot.innerHTML = `
    <a class="skip-link" href="#main-content">Skip to main</a>
    <section class="shell">
      <header class="topbar">
        <div class="brand-block">
          <p class="eyebrow">Private household tracker</p>
          <h1>Health Monitor</h1>
          <p class="topbar-subtitle">${escapeHtml(state.selectedDay)}${state.person ? ` · ${escapeHtml(state.person.name)}` : ""}</p>
        </div>
        <div class="topbar-actions">
          ${renderConnectionStatus()}
          ${renderProfileSwitcher("topbar")}
        </div>
      </header>

      ${renderAppNav(activePage, needsSetup)}
      ${renderNoticeBanner()}

      <main class="page-shell" id="main-content">
        ${needsSetup ? renderSetupPage() : renderPage(activePage)}
      </main>
    </section>
  `;
  bindEvents();
}

function requireAppRoot(): HTMLDivElement {
  const root = document.querySelector<HTMLDivElement>("#app");
  if (!root) {
    throw new Error("missing app root");
  }
  return root;
}

function renderProfileSwitcher(placement: "topbar" | "setup"): string {
  if (!state.household || !state.people.length) {
    return `<div class="person-switch person-switch-empty">No profile</div>`;
  }
  const options = state.people
    .map(
      (person) =>
        `<option value="${person.id}" ${person.id === state.person?.id ? "selected" : ""}>${escapeHtml(person.name)}</option>`
    )
    .join("");
  const label = placement === "topbar" ? "Profile" : "Active person";
  return `
    <label class="person-switch ${placement === "topbar" ? "person-switch-topbar" : ""}">
      <span>${label}</span>
      <select class="profile-select">${options}</select>
    </label>
  `;
}

function renderConnectionStatus(): string {
  const pending = state.offlineOutbox.filter(
    (item) => item.status === "pending" || item.status === "failed" || item.status === "replaying"
  ).length;
  const activeJobs = state.jobs.filter((job) => isActiveJobStatus(job.status)).length;
  const offline = !navigator.onLine;
  return `
    <div class="status-pills" aria-label="System status">
      <span class="status-pill ${offline ? "status-offline" : "status-online"}">${offline ? "Offline" : "Online"}</span>
      ${pending ? `<span class="status-pill status-warning">${pending} outbox</span>` : ""}
      ${activeJobs ? `<span class="status-pill status-active">${activeJobs} job${activeJobs === 1 ? "" : "s"}</span>` : ""}
    </div>
  `;
}

function resolveActivePage(needsSetup: boolean): AppPage {
  if (needsSetup) return "settings";
  const page = window.location.hash.replace(/^#\/?/, "");
  if (
    page === "log" ||
    page === "diary" ||
    page === "review" ||
    page === "library" ||
    page === "work" ||
    page === "settings"
  ) {
    return page;
  }
  return "log";
}

function renderAppNav(activePage: AppPage, needsSetup: boolean): string {
  if (needsSetup) {
    return `
      <nav class="app-nav" aria-label="Primary">
        ${navLink("settings", "Setup", activePage)}
        ${navLink("work", "Work", activePage)}
      </nav>
    `;
  }
  return `
    <nav class="app-nav" aria-label="Primary">
      ${navLink("log", "Log", activePage)}
      ${navLink("diary", "Diary", activePage)}
      ${navLink("review", "Review", activePage)}
      ${navLink("library", "Library", activePage)}
      ${navLink("work", "Work", activePage)}
      ${navLink("settings", "Settings", activePage)}
    </nav>
  `;
}

function navLink(page: AppPage, label: string, activePage: AppPage): string {
  return `<a href="#/${page}" ${page === activePage ? 'aria-current="page"' : ""}>${label}</a>`;
}

function renderNoticeBanner(): string {
  if (state.errorMessage) {
    return `<div class="notice notice-error" role="alert">${escapeHtml(state.errorMessage)}</div>`;
  }
  if (!state.notice) {
    return "";
  }
  return `<div class="notice" role="status" aria-live="polite">${escapeHtml(state.notice)}${
    state.lastDeletedEntry ? ` <button id="undo-delete" type="button">Undo</button>` : ""
  }</div>`;
}

function renderCaptureHub(): string {
  return `
    <section class="capture-zone" id="capture">
      <agent-chat id="log-agent-chat"></agent-chat>
    </section>
  `;
}

function logAgentModes(): AgentChatMode[] {
  return [
    {
      id: "chat",
      label: "Chat",
      description: "Questions and fixes",
      placeholder: `Ask about ${state.selectedDay}, request a correction, or attach a photo for OCR.`
    },
    {
      id: "meal",
      label: "Meal note",
      description: "Foods, portions, context",
      placeholder: "10am\n- 100g queijo\n- cafe com leite\n- banana depois do treino"
    },
    {
      id: "label",
      label: "Product label",
      description: "Photos, code, table",
      placeholder: "Product: name\nBarcode: numbers if visible\nQuantity: 170 g if this should also be logged\nPaste label text here or attach photos."
    },
    {
      id: "recipe",
      label: "Recipe",
      description: "Batch food or prep",
      placeholder: "Recipe: Batch name\nYield: 1000 g\nIngredients:\n- 500g ingredient\nLog grams: 100"
    },
    {
      id: "correction",
      label: "Correction",
      description: "Fix a previous entry",
      placeholder: "Correct yesterday: the cheese was 50g, not 100g."
    },
    {
      id: "review_note",
      label: "Review note",
      description: "Save an observation",
      placeholder: "Create a review note about this week..."
    }
  ];
}

function logAgentState(): AgentChatElementState {
  const status: AgentChatStatus = state.isOfflineReplayRunning
    ? "replaying"
    : !navigator.onLine
      ? "offline"
      : state.errorMessage
        ? "failed"
        : "idle";
  const mode = logAgentModes().find((candidate) => candidate.id === state.logMode);
  return {
    messages: logAgentMessages(),
    modes: logAgentModes(),
    activeModeId: mode?.id ?? "chat",
    status,
    attachments: [],
    composer: {
      disabled: !state.person,
      allowAttachments: state.logMode === "chat" || state.logMode === "label",
      accept: "image/*",
      multiple: true,
      label: "Message",
      sendLabel: state.logMode === "chat" || state.logMode === "correction" || state.logMode === "review_note" ? "Send" : "Draft proposal",
      helperText: logAgentHelperText(state.logMode),
      showInspectPrompt: true
    }
  };
}

function logAgentHelperText(mode: LogMode): string {
  if (mode === "label") return "Attach one or more photos. Add barcode, pasted table text, or quantity in the message when useful.";
  if (mode === "recipe") return "Describe the batch, yield, ingredients, and optional portion to log.";
  if (mode === "meal") return "Use multiple lines for foods and portions. The agent drafts; you still review before applying.";
  if (mode === "correction") return "Describe the mistake and the desired correction. The agent can draft a proposal.";
  if (mode === "review_note") return "Ask the agent to summarize an observation or pattern as a review note.";
  return "Attach label photos when useful. Chat can queue work for the background worker.";
}

function logAgentMessages(): AgentChatMessage[] {
  const messages: AgentChatMessage[] = [];
  for (const event of state.logEvents.slice(-8)) {
    messages.push({
      id: `${event.id}_user`,
      role: "user",
      createdAt: event.created_at,
      text: `${event.title}\n${event.message}`
    });
    messages.push({
      id: `${event.id}_assistant`,
      role: "assistant",
      createdAt: event.created_at,
      text: event.result,
      toolCalls: [
        {
          id: `${event.id}_tool`,
          name: jobLabelForLogMode(event.mode),
          status: event.result.toLowerCase().includes("offline") ? "pending" : "succeeded",
          summary: event.title
        }
      ]
    });
  }
  if (state.chatResponse) {
    messages.push({
      id: `chat_response_${state.chatResponse.run_id}`,
      role: "assistant",
      createdAt: new Date().toISOString(),
      text: state.chatResponse.message,
      toolCalls: [
        {
          id: `chat_response_tool_${state.chatResponse.run_id}`,
          name: state.chatResponse.behavior_label,
          status: "succeeded",
          summary: `${state.chatResponse.citations.length} citation${state.chatResponse.citations.length === 1 ? "" : "s"}`
        }
      ]
    });
  }
  if (state.proposal) {
    messages.push({
      id: `proposal_${state.proposal.id}`,
      role: "assistant",
      createdAt: state.proposal.created_at,
      text: "A proposal is ready for review.",
      draftCards: [proposalToDraftCard(state.proposal)]
    });
  }
  return messages;
}

function proposalToDraftCard(proposal: Proposal): AgentChatDraftCard {
  return {
    id: proposal.id,
    kind: proposalKindToDraftKind(proposal.proposal_type),
    title: proposal.proposal_type.replaceAll("_", " "),
    summary: proposal.summary,
    details: `${Math.round(proposal.totals.calories_kcal)} kcal · ${proposal.entries.length} entr${proposal.entries.length === 1 ? "y" : "ies"}`,
    status: proposal.status === "draft" ? "needs_review" : proposal.status === "confirmed" ? "confirmed" : "rejected"
  };
}

function proposalKindToDraftKind(kind: string): AgentChatDraftCard["kind"] {
  if (kind.includes("meal")) return "meal";
  if (kind.includes("label") || kind.includes("food")) return "label";
  if (kind.includes("recipe")) return "recipe";
  if (kind.includes("correction")) return "correction";
  if (kind.includes("review")) return "review_note";
  return "generic";
}

function jobLabelForLogMode(mode: LogMode): string {
  if (mode === "meal") return "Meal note";
  if (mode === "label") return "Product label";
  if (mode === "recipe") return "Recipe";
  if (mode === "correction") return "Correction";
  if (mode === "review_note") return "Review note";
  return "Agent chat";
}

function renderSetupPage(): string {
  return `
    <section class="page-header">
      <div>
        <p class="eyebrow">Start here</p>
        <h2>Household setup</h2>
        <p>Create the household and first profile before logging meals.</p>
      </div>
    </section>
    <section class="page-grid two-column">
      <div class="primary">
        ${renderSetup()}
      </div>
      <aside class="side">
        ${state.offlineOutbox.length || !navigator.onLine ? renderOfflineOutbox() : ""}
        ${state.jobs.length ? renderJobs() : ""}
        ${renderDataPortability()}
      </aside>
    </section>
  `;
}

function renderPage(page: AppPage): string {
  if (page === "diary") return renderDiaryPage();
  if (page === "review") return renderReviewPage();
  if (page === "library") return renderLibraryPage();
  if (page === "work") return renderWorkPage();
  if (page === "settings") return renderSettingsPage();
  return renderLogPage();
}

function renderLogPage(): string {
  return `
    ${renderPageHeader("Log", "Capture meals, labels, recipes, and loose agent notes.", [
      state.selectedDay,
      state.person?.name ?? "No profile"
    ])}
    <section class="page-grid two-column">
      <div class="primary">
        ${renderCaptureHub()}
      </div>
      <aside class="side">
        ${renderProposal()}
        ${renderOfflineOutbox()}
      </aside>
    </section>
  `;
}

function renderDiaryPage(): string {
  return `
    ${renderPageHeader("Diary", "Review and correct the selected day.", [state.selectedDay])}
    <section class="page-grid two-column wide-primary">
      <div class="primary">
        ${renderToday()}
      </div>
      <aside class="side">
        ${renderManualLog()}
        ${renderWeightForm()}
      </aside>
    </section>
  `;
}

function renderReviewPage(): string {
  return `
    ${renderPageHeader("Review", "Weekly macro trends, weight movement, and saved review notes.", [])}
    <section class="page-grid single-column">
      ${renderReview()}
    </section>
  `;
}

function renderLibraryPage(): string {
  return `
    ${renderPageHeader("Library", "Manage food versions, labels, barcode references, and external lookups.", [])}
    <section class="page-grid two-column">
      <div class="primary" id="library-admin">
        ${renderFoodLookup()}
        ${renderFoodForm()}
      </div>
      <aside class="side">
        ${renderProposal()}
        ${renderProposalInbox()}
      </aside>
    </section>
  `;
}

function renderWorkPage(): string {
  return `
    ${renderPageHeader("Work", "Background jobs, offline outbox, proposal history, and agent audit trail.", [
      navigator.onLine ? "Online" : "Offline"
    ])}
    <section class="page-grid two-column">
      <div class="primary">
        ${renderJobs()}
        ${renderOfflineOutbox()}
      </div>
      <aside class="side">
        ${renderProposal()}
        ${renderProposalInbox()}
        ${renderAgentChat()}
      </aside>
    </section>
  `;
}

function renderSettingsPage(): string {
  return `
    ${renderPageHeader("Settings", "Household profiles, macro targets, and data portability.", [])}
    <section class="page-grid two-column">
      <div class="primary">
        ${renderSetup()}
        ${renderGoalForm()}
      </div>
      <aside class="side">
        ${renderDataPortability()}
      </aside>
    </section>
  `;
}

function renderPageHeader(title: string, subtitle: string, chips: string[]): string {
  const visibleChips = chips.filter(Boolean);
  return `
    <section class="page-header">
      <div>
        <p class="eyebrow">Workspace</p>
        <h2>${escapeHtml(title)}</h2>
        <p>${escapeHtml(subtitle)}</p>
      </div>
      ${
        visibleChips.length
          ? `<div class="capture-context">${visibleChips.map((chip) => `<span>${escapeHtml(chip)}</span>`).join("")}</div>`
          : ""
      }
    </section>
  `;
}

function renderToday(): string {
  const summary = state.summary;
  const totals = summary?.totals ?? zeroNutrients();
  const target = summary?.target;
  const delta = summary?.target_delta;
  const meals = summary?.meals ?? {};
  const mealSections = Object.entries(meals)
    .map(([meal, entries]) => {
      const rows = entries
        .map(
          (entry) => `
            <tr>
              <td>
                <strong>${escapeHtml(entry.food_name)}</strong>
                <span>${escapeHtml(entry.food_version_label)} · ${escapeHtml(entry.source)} ${evidenceBadge(entry)}</span>
                <span>${entry.nutrients.fiber_g} g fiber · ${entry.nutrients.sodium_mg} mg sodium</span>
                <form class="entry-edit-form" data-entry-id="${entry.id}">
                  <input name="quantity_g" type="number" step="0.1" value="${entry.quantity_g}" aria-label="Quantity grams" />
                  <select name="meal_type" aria-label="Meal type">${mealOptions(entry.meal_type)}</select>
                  <button type="submit">Update</button>
                  <button class="entry-delete" type="button" data-entry-id="${entry.id}">Delete</button>
                </form>
              </td>
              <td>${entry.quantity_g} g</td>
              <td>${entry.nutrients.calories_kcal} kcal</td>
              <td>${entry.nutrients.protein_g} g</td>
            </tr>
          `
        )
        .join("");
      return `
        <section class="meal-band">
          <h3>${escapeHtml(titleCase(meal))}</h3>
          <table>
            <thead><tr><th>Food</th><th>Qty</th><th>Calories</th><th>Protein</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </section>
      `;
    })
    .join("");

  return `
    <section class="today" id="today-summary">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Today</p>
          <h2>${summary?.day ?? state.selectedDay}</h2>
        </div>
        <div class="date-actions">
          <label>Day <input id="selected-day" type="date" value="${state.selectedDay}" /></label>
          <button id="refresh-summary" type="button">Refresh</button>
        </div>
      </div>
      <div class="metrics">
        ${metric("Calories", `${totals.calories_kcal}`, "kcal")}
        ${metric("Protein", `${totals.protein_g}`, "g")}
        ${metric("Carbs", `${totals.carbs_g}`, "g")}
        ${metric("Fat", `${totals.fat_g}`, "g")}
        ${metric("Fiber", `${totals.fiber_g}`, "g")}
        ${metric("Sodium", `${totals.sodium_mg}`, "mg")}
      </div>
      ${
        target && delta
          ? `<div class="target-strip">
              <span>Target ${target.calories_kcal} kcal</span>
              <span>${signed(delta.calories_kcal)} kcal</span>
              <span>${signed(delta.protein_g)} g protein</span>
              <span>${signed(delta.fiber_g)} g fiber</span>
              <span>${signed(delta.sodium_mg)} mg sodium</span>
            </div>`
          : ""
      }
      ${mealSections || `<p class="empty">No diary entries for this day yet.</p>`}
    </section>
  `;
}

function renderReview(): string {
  const week = state.week;
  const trend = state.weightTrend;
  const totals = week?.totals ?? zeroNutrients();
  const averages = week?.averages ?? zeroNutrients();
  const dailyRows = week
    ? Object.entries(week.daily)
        .map(
          ([day, nutrients]) => {
            const target = week.daily_targets[day];
            return `
            <tr>
              <td>${escapeHtml(day)}</td>
              <td>${nutrients.calories_kcal}</td>
              <td>${nutrients.protein_g} g</td>
              <td>${target ? `${target.calories_kcal}` : ""}</td>
              <td>${nutrients.carbs_g} g</td>
              <td>${nutrients.fat_g} g</td>
              <td>${nutrients.fiber_g} g</td>
              <td>${nutrients.sodium_mg} mg</td>
            </tr>
          `;
          }
        )
        .join("")
    : "";
  const weightRows = trend
    ? trend.entries
        .map(
          (entry) => `
            <tr>
              <td>
                <strong>${escapeHtml(entry.measured_at.slice(0, 10))}</strong>
                <form class="weight-edit-form" data-weight-id="${entry.id}">
                  <input name="measured_at_local" type="datetime-local" value="${escapeHtml(entry.measured_at.slice(0, 16))}" aria-label="Measured at" />
                  <input name="weight_kg" type="number" step="0.1" value="${entry.weight_kg}" aria-label="Weight kg" />
                  <input name="note" value="${escapeHtml(entry.note ?? "")}" aria-label="Weight note" />
                  <button type="submit">Update</button>
                </form>
              </td>
              <td>${entry.weight_kg} kg</td>
              <td>${escapeHtml(entry.note ?? "")}</td>
            </tr>
          `
        )
        .join("")
    : "";
  const noteRows = state.reviewNotes
    .map(
      (note) => `
        <li>
          <strong>${escapeHtml(note.title)}</strong>
          <span>${escapeHtml(note.starts_on ?? "undated")}${note.ends_on ? ` to ${escapeHtml(note.ends_on)}` : ""} · ${escapeHtml(note.source)}</span>
          <p>${escapeHtml(note.body)}</p>
        </li>
      `
    )
    .join("");
  return `
    <section class="today" id="weekly-review">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Review</p>
          <h2>${week ? `${week.start} to ${week.end}` : "Weekly trend"}</h2>
        </div>
        <button id="refresh-review" type="button" ${state.person ? "" : "disabled"}>Refresh</button>
      </div>
      <div class="metrics">
        ${metric("Week kcal", `${totals.calories_kcal}`, "total")}
        ${metric("Avg kcal", `${averages.calories_kcal}`, "daily")}
        ${metric("Protein", `${totals.protein_g}`, "g total")}
        ${metric("Weight", `${trend?.delta_kg ?? 0}`, "kg delta")}
        ${metric("Fiber", `${averages.fiber_g}`, "g avg")}
        ${metric("Sodium", `${averages.sodium_mg}`, "mg avg")}
      </div>
      <div class="chart-grid">
        ${week ? renderMacroChart(week) : ""}
        ${trend?.entries.length ? renderWeightTrendChart(trend) : ""}
      </div>
      ${
        dailyRows
          ? `<table><thead><tr><th>Day</th><th>Calories</th><th>Protein</th><th>Target</th><th>Carbs</th><th>Fat</th><th>Fiber</th><th>Sodium</th></tr></thead><tbody>${dailyRows}</tbody></table>`
          : `<p class="empty">No weekly review loaded yet.</p>`
      }
      ${
        weightRows
          ? `<section class="meal-band"><h3>Weights</h3><table><thead><tr><th>Date</th><th>Weight</th><th>Note</th></tr></thead><tbody>${weightRows}</tbody></table></section>`
          : ""
      }
      ${
        noteRows
          ? `<section class="meal-band"><h3>Review notes</h3><ul class="evidence-list">${noteRows}</ul></section>`
          : ""
      }
    </section>
  `;
}

function renderProposal(): string {
  if (!state.proposal) {
    return `
      <section class="proposal-empty" id="proposal-review">
        <p class="eyebrow">Agent proposal</p>
        <h2>No pending proposal</h2>
      </section>
    `;
  }
  const entries = state.proposal.entries
    .map(
      (entry) => {
        const editable = state.proposal?.status === "draft";
        return `
        <li>
          <strong>${escapeHtml(entry.food_name)}</strong>
          <span>${entry.quantity_g} g · ${entry.nutrients.calories_kcal} kcal · ${entry.nutrients.protein_g} g protein</span>
          <span>${entry.nutrients.fiber_g} g fiber · ${entry.nutrients.sodium_mg} mg sodium</span>
          ${
            editable
              ? `<form class="proposal-entry-edit-form" data-entry-id="${entry.id}">
                  <label>Food
                    <select name="food_version_id">${proposalFoodOptions(entry)}</select>
                  </label>
                  <label>Quantity
                    <input name="quantity_g" type="number" step="0.1" value="${entry.quantity_g}" />
                  </label>
                  <label>Meal
                    <select name="meal_type">${mealOptions(entry.meal_type)}</select>
                  </label>
                  <button type="submit">Update</button>
                </form>`
              : ""
          }
        </li>
      `;
      }
    )
    .join("");
  const payloadDetails =
    state.proposal.proposal_type === "food_version_from_label" ||
    state.proposal.proposal_type === "food_version_from_lookup"
      ? renderFoodVersionProposalPayload(state.proposal)
      : state.proposal.proposal_type === "recipe_food_version" ||
          state.proposal.proposal_type === "recipe_draft"
        ? renderRecipeProposalPayload(state.proposal)
      : state.proposal.proposal_type === "diary_entry_update"
        ? renderDiaryUpdateProposalPayload(state.proposal)
      : state.proposal.proposal_type === "diary_entries_with_estimates"
        ? renderEstimateProposalPayload(state.proposal)
      : state.proposal.proposal_type === "review_note"
        ? renderReviewNoteProposalPayload(state.proposal)
      : state.proposal.status === "needs_clarification"
        ? renderClarificationProposalPayload(state.proposal)
      : "";
  const evidence = state.proposal.evidence
    .map(
      (item) => `
        <li>
          <strong>${escapeHtml(String(item.source_text ?? item.phrase ?? "item"))}</strong>
          <span>${escapeHtml(String(item.resolution_reason ?? "evidence"))} · ${escapeHtml(String(item.quantity_g ?? ""))} g</span>
        </li>
      `
    )
    .join("");
  const settings = state.proposal.agent_run
    ? Object.entries(state.proposal.agent_run.settings)
        .map(([key, value]) => `${key}: ${String(value)}`)
        .join(" · ")
    : "no run settings";
  const canConfirm = state.proposal.status === "draft";
  const canReject = state.proposal.status === "draft" || state.proposal.status === "needs_clarification";
  return `
    <section class="proposal" id="proposal-review">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Agent proposal</p>
          <h2>${escapeHtml(state.proposal.status)}</h2>
          <p>${escapeHtml(state.proposal.summary)}</p>
        </div>
        <div class="button-row">
          ${canReject ? `<button id="reject-proposal" type="button">Reject</button>` : ""}
          ${canConfirm ? `<button id="confirm-proposal" class="primary-action" type="button">Confirm</button>` : ""}
        </div>
      </div>
      ${renderProposalAudit(state.proposal)}
      ${renderAgentToolTrace(state.proposal)}
      <div class="metrics compact">
        ${metric("Calories", `${state.proposal.totals.calories_kcal}`, "kcal")}
        ${metric("Protein", `${state.proposal.totals.protein_g}`, "g")}
        ${metric("Carbs", `${state.proposal.totals.carbs_g}`, "g")}
        ${metric("Fat", `${state.proposal.totals.fat_g}`, "g")}
      </div>
      ${entries ? `<ul class="proposal-list">${entries}</ul>` : ""}
      ${payloadDetails}
      <p class="hint">${escapeHtml(settings)}</p>
      ${evidence ? `<ul class="evidence-list">${evidence}</ul>` : ""}
    </section>
  `;
}

function renderAgentToolTrace(proposal: Proposal): string {
  const calls = proposal.agent_run?.tool_calls ?? [];
  if (!calls.length) return "";
  const rows = calls
    .map(
      (call) => `
        <li>
          <div>
            <strong>${escapeHtml(toolCallLabel(call.tool_name))}</strong>
            <span class="tool-status ${toolStatusClass(call.status)}">${escapeHtml(call.status)}</span>
          </div>
          <span>${escapeHtml(call.input_summary)}</span>
          <span>${escapeHtml(call.output_summary)}</span>
          ${
            call.error
              ? `<span class="tool-error">${escapeHtml(call.error)}</span>`
              : ""
          }
        </li>
      `
    )
    .join("");
  return `
    <section class="tool-trace" aria-label="Agent tool trace">
      <div class="tool-trace-heading">
        <h3>Agent trace</h3>
        <span>${calls.length} call${calls.length === 1 ? "" : "s"}</span>
      </div>
      <ol class="tool-call-list">${rows}</ol>
    </section>
  `;
}

function renderProposalAudit(proposal: Proposal): string {
  const supersededBy =
    typeof proposal.payload.superseded_by_proposal_id === "string"
      ? proposal.payload.superseded_by_proposal_id
      : null;
  const run = proposal.agent_run;
  return `
    <dl class="audit-list">
      <div><dt>Created</dt><dd>${escapeHtml(formatDateTime(proposal.created_at))}</dd></div>
      ${
        run
          ? `<div><dt>Runtime</dt><dd>${escapeHtml(run.runtime ?? "deterministic")} · ${escapeHtml(run.model_name ?? "deterministic")} · ${run.tool_loop_count} loop${run.tool_loop_count === 1 ? "" : "s"}</dd></div>`
          : ""
      }
      ${
        run?.fallback_reason
          ? `<div><dt>Fallback</dt><dd>${escapeHtml(run.fallback_reason)}</dd></div>`
          : ""
      }
      ${
        proposal.confirmed_at
          ? `<div><dt>Confirmed</dt><dd>${escapeHtml(formatDateTime(proposal.confirmed_at))}</dd></div>`
          : ""
      }
      ${
        proposal.rejected_at
          ? `<div><dt>Rejected</dt><dd>${escapeHtml(formatDateTime(proposal.rejected_at))}</dd></div>`
          : ""
      }
      ${
        supersededBy
          ? `<div><dt>Superseded by</dt><dd><button class="proposal-load-related" type="button" data-proposal-id="${escapeHtml(supersededBy)}">${escapeHtml(supersededBy)}</button></dd></div>`
          : ""
      }
      ${
        proposal.applied_record_ids.length
          ? `<div><dt>Applied records</dt><dd>${proposal.applied_record_ids.length}</dd></div>`
          : ""
      }
    </dl>
  `;
}

function toolCallLabel(toolName: string): string {
  return toolName
    .split("_")
    .filter(Boolean)
    .map((word) => word.slice(0, 1).toUpperCase() + word.slice(1))
    .join(" ");
}

function toolStatusClass(status: string): string {
  return status === "failed" ? "tool-status-failed" : "tool-status-completed";
}

function renderProposalInbox(): string {
  const disabled = state.person ? "" : "disabled";
  const rows = state.proposalQueue
    .slice(0, 8)
    .map((proposal) => {
      const active = proposal.status === "draft" || proposal.status === "needs_clarification";
      return `
        <li>
          <div>
            <strong>${escapeHtml(proposal.summary || proposal.proposal_type)}</strong>
            <span${active ? ' class="proposal-status-active"' : ""}>${escapeHtml(proposal.status)} · ${escapeHtml(proposal.proposal_type)} · ${escapeHtml(formatDateTime(proposal.created_at))}</span>
            <span>${proposal.totals.calories_kcal} kcal · ${proposal.totals.protein_g} g protein</span>
          </div>
          <button class="proposal-open" type="button" data-proposal-id="${escapeHtml(proposal.id)}">Open</button>
        </li>
      `;
    })
    .join("");
  return `
    <section class="today">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Proposal inbox</p>
          <h2>Recent drafts and history</h2>
        </div>
        <button id="refresh-proposals" type="button" ${disabled}>Refresh</button>
      </div>
      ${
        rows
          ? `<ul class="proposal-inbox-list">${rows}</ul>`
          : `<p class="empty">No proposals for this profile yet.</p>`
      }
    </section>
  `;
}

function renderMacroChart(week: WeekSummary): string {
  const days = Object.keys(week.daily).sort();
  if (!days.length) return "";
  const width = 640;
  const height = 180;
  const padding = { top: 18, right: 18, bottom: 34, left: 42 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const values = days.flatMap((day) => [
    week.daily[day]?.calories_kcal ?? 0,
    week.daily_targets[day]?.calories_kcal ?? 0
  ]);
  const maxValue = Math.max(1, ...values);
  const step = chartWidth / days.length;
  const barWidth = Math.min(34, step * 0.52);
  const bars = days
    .map((day, index) => {
      const calories = week.daily[day]?.calories_kcal ?? 0;
      const target = week.daily_targets[day]?.calories_kcal ?? 0;
      const x = padding.left + index * step + (step - barWidth) / 2;
      const barHeight = (calories / maxValue) * chartHeight;
      const y = padding.top + chartHeight - barHeight;
      const targetY = padding.top + chartHeight - (target / maxValue) * chartHeight;
      return `
        <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barHeight.toFixed(1)}" rx="4" />
        ${
          target
            ? `<line x1="${(x - 4).toFixed(1)}" y1="${targetY.toFixed(1)}" x2="${(x + barWidth + 4).toFixed(1)}" y2="${targetY.toFixed(1)}" class="target-marker" />`
            : ""
        }
        <text x="${(x + barWidth / 2).toFixed(1)}" y="${height - 12}" text-anchor="middle">${escapeHtml(day.slice(5))}</text>
      `;
    })
    .join("");
  const gridLines = [0.25, 0.5, 0.75, 1]
    .map((ratio) => {
      const y = padding.top + chartHeight - chartHeight * ratio;
      return `<line x1="${padding.left}" y1="${y.toFixed(1)}" x2="${width - padding.right}" y2="${y.toFixed(1)}" class="grid-line" />`;
    })
    .join("");
  return `
    <section class="chart-panel" aria-label="Weekly calories chart">
      <div class="chart-heading">
        <h3>Calories vs target</h3>
        <span>${week.start} to ${week.end}</span>
      </div>
      <svg class="chart-svg macro-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Daily calories compared with calorie target">
        ${gridLines}
        <line x1="${padding.left}" y1="${padding.top + chartHeight}" x2="${width - padding.right}" y2="${padding.top + chartHeight}" class="axis-line" />
        ${bars}
      </svg>
      <div class="chart-legend">
        <span><i class="legend-box actual"></i> Calories</span>
        <span><i class="legend-line"></i> Target</span>
      </div>
    </section>
  `;
}

function renderWeightTrendChart(trend: WeightTrend): string {
  const entries = [...trend.entries].sort((left, right) => left.measured_at.localeCompare(right.measured_at));
  if (!entries.length) return "";
  const width = 640;
  const height = 180;
  const padding = { top: 18, right: 18, bottom: 34, left: 42 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const weights = entries.map((entry) => entry.weight_kg);
  const min = Math.min(...weights);
  const max = Math.max(...weights);
  const span = Math.max(1, max - min);
  const points = entries.map((entry, index) => {
    const x = padding.left + (entries.length === 1 ? chartWidth / 2 : (index / (entries.length - 1)) * chartWidth);
    const y = padding.top + chartHeight - ((entry.weight_kg - min) / span) * chartHeight;
    return { entry, x, y };
  });
  const linePoints = points.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
  const markers = points
    .map(
      (point) => `
        <circle cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="5" />
        <text x="${point.x.toFixed(1)}" y="${height - 12}" text-anchor="middle">${escapeHtml(point.entry.measured_at.slice(5, 10))}</text>
      `
    )
    .join("");
  const mid = min + span / 2;
  return `
    <section class="chart-panel" aria-label="Weight trend chart">
      <div class="chart-heading">
        <h3>Weight trend</h3>
        <span>${trend.latest_kg ?? 0} kg latest · ${signed(trend.delta_kg ?? 0)} kg</span>
      </div>
      <svg class="chart-svg weight-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Weight entries over time">
        <line x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${padding.top + chartHeight}" class="axis-line" />
        <line x1="${padding.left}" y1="${padding.top + chartHeight}" x2="${width - padding.right}" y2="${padding.top + chartHeight}" class="axis-line" />
        <text x="8" y="${(padding.top + 5).toFixed(1)}">${max.toFixed(1)}</text>
        <text x="8" y="${(padding.top + chartHeight / 2 + 5).toFixed(1)}">${mid.toFixed(1)}</text>
        <text x="8" y="${(padding.top + chartHeight + 5).toFixed(1)}">${min.toFixed(1)}</text>
        ${entries.length > 1 ? `<polyline points="${linePoints}" />` : ""}
        ${markers}
      </svg>
      <div class="chart-legend">
        <span><i class="legend-box weight"></i> Weight kg</span>
      </div>
    </section>
  `;
}

function renderJobs(): string {
  const disabled = state.person ? "" : "disabled";
  const rows = state.jobs
    .map((job) => {
      const proposalId = typeof job.result.proposal_id === "string" ? job.result.proposal_id : null;
      const chatTurnId = typeof job.result.chat_turn_id === "string" ? job.result.chat_turn_id : null;
      const active = isActiveJobStatus(job.status);
      return `
        <li>
          <div>
            <strong>${escapeHtml(jobLabel(job.job_type))}</strong>
            <span${active ? ' class="job-status-active"' : ""}>${escapeHtml(job.status)} · ${job.attempts} attempt${job.attempts === 1 ? "" : "s"} · ${escapeHtml(job.created_at.slice(0, 19))}</span>
            ${
              job.last_error
                ? `<span class="job-error">${escapeHtml(job.last_error)}</span>`
                : proposalId
                  ? `<span>Proposal ${escapeHtml(proposalId)}</span>`
                  : chatTurnId
                    ? `<span>Chat turn ${escapeHtml(chatTurnId)}</span>`
                  : ""
            }
          </div>
          <div class="button-row">
            ${
              job.status === "pending"
                ? `<button class="job-process" type="button" data-job-id="${job.id}">Process</button>`
                : ""
            }
            ${
              proposalId
                ? `<button class="job-load-proposal" type="button" data-proposal-id="${escapeHtml(proposalId)}">Open proposal</button>`
                : ""
            }
            ${
              chatTurnId
                ? `<button class="job-open-chat" type="button" data-chat-turn-id="${escapeHtml(chatTurnId)}">Open chat</button>`
                : ""
            }
          </div>
        </li>
      `;
    })
    .join("");
  return `
    <section class="today">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Worker</p>
          <h2>Background jobs</h2>
        </div>
        <button id="refresh-jobs" type="button" ${disabled}>Refresh</button>
      </div>
      ${
        rows
          ? `<ul class="job-list">${rows}</ul>`
          : `<p class="empty">No background jobs for this profile.</p>`
      }
    </section>
  `;
}

function renderOfflineOutbox(): string {
  const rows = state.offlineOutbox
    .slice()
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .map((item) => {
      const active = item.status === "pending" || item.status === "replaying";
      return `
        <li>
          <div>
            <strong>${escapeHtml(jobLabel(item.kind))}</strong>
            <span${active ? ' class="job-status-active"' : ""}>${escapeHtml(item.status)} · ${item.attempts} attempt${item.attempts === 1 ? "" : "s"} · ${escapeHtml(item.created_at.slice(0, 19))}</span>
            <span>${escapeHtml(item.selected_day)} · ${item.files.length} upload${item.files.length === 1 ? "" : "s"}</span>
            ${item.last_error ? `<span class="job-error">${escapeHtml(item.last_error)}</span>` : ""}
          </div>
          <div class="button-row">
            ${
              item.status === "pending" || item.status === "failed"
                ? `<button class="offline-retry" type="button" data-outbox-id="${escapeHtml(item.id)}">Retry</button>`
                : ""
            }
            ${
              item.status !== "replaying"
                ? `<button class="offline-delete" type="button" data-outbox-id="${escapeHtml(item.id)}">Delete</button>`
                : ""
            }
          </div>
        </li>
      `;
    })
    .join("");
  const connection = navigator.onLine ? "online" : "waiting for connection";
  return `
    <section class="today offline-outbox" aria-label="Offline outbox">
      <div class="section-heading">
        <div>
          <p class="eyebrow">PWA outbox</p>
          <h2>Offline notes</h2>
        </div>
        <button id="replay-offline-outbox" type="button" ${state.isOfflineReplayRunning ? "disabled" : ""}>Retry all</button>
      </div>
      <p class="hint">${escapeHtml(connection)} · Offline capture is ready. Agent work runs after reconnect.</p>
      ${
        rows
          ? `<ul class="job-list offline-list">${rows}</ul>`
          : `<p class="empty">No offline notes waiting to replay.</p>`
      }
    </section>
  `;
}

function renderFoodVersionProposalPayload(proposal: Proposal): string {
  const nutrients = proposal.payload.nutrients_per_100g as Partial<Nutrients> | undefined;
  return `
    <dl class="payload-grid">
      <div><dt>Food</dt><dd>${escapeHtml(String(proposal.payload.food_name ?? ""))}</dd></div>
      <div><dt>Brand</dt><dd>${escapeHtml(String(proposal.payload.brand ?? ""))}</dd></div>
      <div><dt>Serving</dt><dd>${escapeHtml(String(proposal.payload.serving_size_g ?? ""))} g</dd></div>
      <div><dt>Barcode</dt><dd>${escapeHtml(String(proposal.payload.barcode ?? ""))}</dd></div>
      <div><dt>Calories / 100g</dt><dd>${nutrients?.calories_kcal ?? 0}</dd></div>
      <div><dt>Protein / 100g</dt><dd>${nutrients?.protein_g ?? 0} g</dd></div>
      <div><dt>Fiber / 100g</dt><dd>${nutrients?.fiber_g ?? 0} g</dd></div>
      <div><dt>Sodium / 100g</dt><dd>${nutrients?.sodium_mg ?? 0} mg</dd></div>
    </dl>
  `;
}

function renderEstimateProposalPayload(proposal: Proposal): string {
  const estimates = proposal.payload.estimated_food_versions as
    | Array<Record<string, unknown>>
    | undefined;
  if (!estimates?.length) return "";
  const items = estimates
    .map((estimate) => {
      const nutrients = estimate.nutrients_per_100g as Partial<Nutrients> | undefined;
      return `
        <div>
          <dt>${escapeHtml(String(estimate.food_name ?? ""))}</dt>
          <dd>${escapeHtml(String(estimate.source ?? "estimate"))} · confidence ${escapeHtml(String(estimate.confidence ?? ""))}</dd>
          <dd>${nutrients?.calories_kcal ?? 0} kcal · ${nutrients?.protein_g ?? 0} g protein / 100g</dd>
        </div>
      `;
    })
    .join("");
  return `<dl class="payload-grid">${items}</dl>`;
}

function renderClarificationProposalPayload(proposal: Proposal): string {
  const unresolvedItems = proposal.payload.unresolved_items as
    | Array<Record<string, unknown>>
    | undefined;
  if (!unresolvedItems?.length) return "";
  return unresolvedItems
    .map((item, index) => {
      const candidates = item.candidates as Array<Record<string, unknown>> | undefined;
      const candidateRows = candidates
        ?.map((candidate) => {
          const nutrients = candidate.nutrients_per_100g as Partial<Nutrients> | undefined;
          return `
            <li>
              <strong>${escapeHtml(String(candidate.food_name ?? ""))}</strong>
              <span>${escapeHtml(String(candidate.brand ?? ""))} · ${escapeHtml(String(candidate.version_label ?? ""))}</span>
              <span>${nutrients?.calories_kcal ?? 0} kcal · ${nutrients?.protein_g ?? 0} g protein / 100g</span>
              <button
                class="clarification-candidate"
                type="button"
                data-unresolved-index="${index}"
                data-food-version-id="${escapeHtml(String(candidate.food_version_id ?? ""))}"
              >Use this food</button>
            </li>
          `;
        })
        .join("");
      return `
        <section class="meal-band">
          <h3>${escapeHtml(String(item.phrase ?? item.source_text ?? "Clarification"))}</h3>
          ${candidateRows ? `<ul class="lookup-list">${candidateRows}</ul>` : `<p class="empty">No candidate choices available.</p>`}
        </section>
      `;
    })
    .join("");
}

function renderDiaryUpdateProposalPayload(proposal: Proposal): string {
  return `
    <dl class="payload-grid">
      <div><dt>Food</dt><dd>${escapeHtml(String(proposal.payload.food_name ?? ""))}</dd></div>
      <div><dt>Day</dt><dd>${escapeHtml(String(proposal.payload.day ?? ""))}</dd></div>
      <div><dt>Previous</dt><dd>${escapeHtml(String(proposal.payload.previous_quantity_g ?? ""))} g</dd></div>
      <div><dt>New</dt><dd>${escapeHtml(String(proposal.payload.quantity_g ?? ""))} g</dd></div>
    </dl>
  `;
}

function renderReviewNoteProposalPayload(proposal: Proposal): string {
  return `
    <dl class="payload-grid">
      <div><dt>Range</dt><dd>${escapeHtml(String(proposal.payload.starts_on ?? "undated"))}${proposal.payload.ends_on ? ` to ${escapeHtml(String(proposal.payload.ends_on))}` : ""}</dd></div>
      <div><dt>Type</dt><dd>${escapeHtml(String(proposal.payload.note_type ?? "review"))}</dd></div>
      <div><dt>Title</dt><dd>${escapeHtml(String(proposal.payload.title ?? ""))}</dd></div>
      <div><dt>Source</dt><dd>${escapeHtml(String(proposal.payload.source ?? ""))}</dd></div>
    </dl>
    <section class="chat-answer">
      <strong>Body</strong>
      <p>${escapeHtml(String(proposal.payload.body ?? ""))}</p>
    </section>
  `;
}

function renderRecipeProposalPayload(proposal: Proposal): string {
  const nutrients = proposal.payload.nutrients_per_100g as Partial<Nutrients> | undefined;
  const total = proposal.payload.nutrients_total as Partial<Nutrients> | undefined;
  const ingredients = proposal.payload.ingredients as Array<Record<string, unknown>> | undefined;
  const missingFields = proposal.payload.missing_fields as string[] | undefined;
  const preciseLoggingEnabled = proposal.payload.precise_logging_enabled !== false;
  const ingredientRows = ingredients
    ?.map(
      (ingredient) => `
        <li>
          <strong>${escapeHtml(String(ingredient.phrase ?? ""))}</strong>
          <span>${escapeHtml(String(ingredient.quantity_g ?? ""))} g · ${escapeHtml(String(ingredient.resolution_reason ?? ""))}</span>
        </li>
      `
    )
    .join("");
  return `
    <dl class="payload-grid">
      <div><dt>Food</dt><dd>${escapeHtml(String(proposal.payload.food_name ?? ""))}</dd></div>
      <div><dt>Status</dt><dd>${preciseLoggingEnabled ? "Precise logging enabled" : "Draft only"}</dd></div>
      <div><dt>Yield</dt><dd>${proposal.payload.yield_g ? `${escapeHtml(String(proposal.payload.yield_g))} g` : "Missing"}</dd></div>
      <div><dt>Calories</dt><dd>${nutrients?.calories_kcal ?? total?.calories_kcal ?? 0}${nutrients ? " / 100g" : " total"}</dd></div>
      <div><dt>Protein</dt><dd>${nutrients?.protein_g ?? total?.protein_g ?? 0} g${nutrients ? " / 100g" : " total"}</dd></div>
    </dl>
    ${missingFields?.length ? `<p class="hint">Missing: ${missingFields.map(escapeHtml).join(", ")}</p>` : ""}
    ${ingredientRows ? `<ul class="evidence-list">${ingredientRows}</ul>` : ""}
  `;
}

function renderSetup(): string {
  if (state.household && state.person) {
    return `
      <section class="panel">
        <p class="eyebrow">Profile</p>
        <h2>${escapeHtml(state.household.name)}</h2>
        ${renderProfileSwitcher("setup")}
        <p>${escapeHtml(state.person.timezone)}${state.person.height_cm ? ` · ${state.person.height_cm} cm` : ""}</p>
      </section>
      <form id="add-person-form" class="panel">
        <p class="eyebrow">Household</p>
        <h2>Add person</h2>
        <label>Name <input name="name" /></label>
        <label>Timezone <input name="timezone" value="${escapeHtml(state.person.timezone)}" /></label>
        <div class="grid-two">
          <label>Birth date <input name="birth_date" type="date" /></label>
          <label>Height cm <input name="height_cm" type="number" step="0.1" /></label>
        </div>
        <div class="grid-two">
          <label>Sex <input name="sex" /></label>
          <label>Activity <input name="activity_level" /></label>
        </div>
        <button type="submit">Add profile</button>
      </form>
    `;
  }
  return `
    <form id="setup-form" class="panel">
      <p class="eyebrow">Setup</p>
      <h2>Household profile</h2>
      <label>Household <input name="household" value="Casa" /></label>
      <label>Name <input name="name" value="Gabriel" /></label>
      <label>Timezone <input name="timezone" value="America/Sao_Paulo" /></label>
      <div class="grid-two">
        <label>Birth date <input name="birth_date" type="date" /></label>
        <label>Height cm <input name="height_cm" type="number" step="0.1" /></label>
      </div>
      <div class="grid-two">
        <label>Sex <input name="sex" /></label>
        <label>Activity <input name="activity_level" value="moderate" /></label>
      </div>
      <div class="grid-two">
        <label>Target kcal <input name="target_calories_kcal" type="number" value="2000" /></label>
        <label>Protein g <input name="target_protein_g" type="number" value="150" /></label>
        <label>Carbs g <input name="target_carbs_g" type="number" value="180" /></label>
        <label>Fat g <input name="target_fat_g" type="number" value="70" /></label>
        <label>Fiber g <input name="target_fiber_g" type="number" value="30" /></label>
        <label>Sodium mg <input name="target_sodium_mg" type="number" value="2300" /></label>
      </div>
      <button class="primary-action" type="submit">Create profile</button>
    </form>
  `;
}

function renderGoalForm(): string {
  const disabled = state.person ? "" : "disabled";
  return `
    <form id="goal-form" class="panel">
      <p class="eyebrow">Targets</p>
      <h2>Macro plan</h2>
      <label>Starts on <input name="starts_on" type="date" value="${state.selectedDay}" ${disabled} /></label>
      <div class="grid-two">
        <label>Calories <input name="calories_kcal" type="number" value="${state.activeGoal?.targets.calories_kcal ?? 2000}" ${disabled} /></label>
        <label>Protein <input name="protein_g" type="number" value="${state.activeGoal?.targets.protein_g ?? 150}" ${disabled} /></label>
        <label>Carbs <input name="carbs_g" type="number" value="${state.activeGoal?.targets.carbs_g ?? 180}" ${disabled} /></label>
        <label>Fat <input name="fat_g" type="number" value="${state.activeGoal?.targets.fat_g ?? 70}" ${disabled} /></label>
        <label>Fiber <input name="goal_fiber_g" type="number" value="${state.activeGoal?.targets.fiber_g ?? 30}" ${disabled} /></label>
        <label>Sodium mg <input name="goal_sodium_mg" type="number" value="${state.activeGoal?.targets.sodium_mg ?? 2300}" ${disabled} /></label>
      </div>
      <label>Notes <input name="notes" value="${escapeHtml(state.activeGoal?.notes ?? "")}" ${disabled} /></label>
      <button type="submit" ${disabled}>Save targets</button>
    </form>
  `;
}

function renderFoodForm(): string {
  const disabled = state.household ? "" : "disabled";
  const filtered = filteredFoods();
  const foods = filtered
    .map(
      (item) => `
        <li>
          <strong>${escapeHtml(foodLabel(item))}</strong>
          ${foodContextLabel(item)}
          <span>${item.version.nutrients_per_100g.calories_kcal} kcal · ${item.version.nutrients_per_100g.protein_g} g protein / 100g</span>
          <span>${item.version.nutrients_per_100g.fiber_g} g fiber · ${item.version.nutrients_per_100g.sodium_mg} mg sodium / 100g</span>
          ${foodEvidenceLabel(item.attachments)}
          <button class="food-archive" type="button" data-food-id="${item.food.id}">Archive</button>
        </li>
      `
    )
    .join("");
  return `
    <form id="food-form" class="panel">
      <p class="eyebrow">Library</p>
      <h2>Food version</h2>
      <label>Name <input name="name" value="Queijo Minas" ${disabled} /></label>
      <label>Brand <input name="brand" placeholder="optional" ${disabled} /></label>
      <label>Label <input name="version_label" value="current" ${disabled} /></label>
      <div class="grid-two">
        <label>Calories <input name="calories_kcal" type="number" step="0.1" value="315" ${disabled} /></label>
        <label>Protein <input name="protein_g" type="number" step="0.1" value="23" ${disabled} /></label>
        <label>Carbs <input name="carbs_g" type="number" step="0.1" value="2.6" ${disabled} /></label>
        <label>Fat <input name="fat_g" type="number" step="0.1" value="23.5" ${disabled} /></label>
        <label>Fiber <input name="fiber_g" type="number" step="0.1" value="0" ${disabled} /></label>
        <label>Sodium mg <input name="sodium_mg" type="number" step="0.1" value="0" ${disabled} /></label>
      </div>
      <label>Serving size g <input name="serving_size_g" type="number" step="0.1" placeholder="optional" ${disabled} /></label>
      <label>Aliases <input name="aliases" value="queijo, queijo minas" ${disabled} /></label>
      <label>Barcode <input name="barcode" placeholder="optional" ${disabled} /></label>
      <button type="submit" ${disabled}>Save food</button>
      <label>Find saved food <input class="food-filter" data-filter-id="library" type="search" value="${escapeHtml(state.foodFilter)}" placeholder="name, brand, alias, barcode" ${state.foods.length ? "" : "disabled"} /></label>
      ${
        foods
          ? `<ul class="lookup-list">${foods}</ul>`
          : state.foods.length
            ? `<p class="hint">No saved foods match this filter.</p>`
            : `<p class="hint">No saved food versions yet.</p>`
      }
    </form>
  `;
}

function renderFoodLookup(): string {
  const disabled = state.household && state.person ? "" : "disabled";
  const candidates = state.lookupCandidates
    .map(
      (candidate) => `
        <li>
          <strong>${escapeHtml(candidate.product_name)}</strong>
          <span>${escapeHtml(candidate.source_name)} · confidence ${candidate.confidence}</span>
          <span>${candidate.nutrients_per_100g.calories_kcal} kcal · ${candidate.nutrients_per_100g.protein_g} g protein / 100g</span>
          ${
            candidate.source_type.startsWith("local_")
              ? `<span>Already saved locally</span>`
              : `<button class="lookup-propose" type="button" data-candidate-id="${candidate.id}">Draft food version</button>`
          }
        </li>
      `
    )
    .join("");
  return `
    <form id="food-lookup-form" class="panel">
      <p class="eyebrow">Lookup</p>
      <h2>Food source</h2>
      <label>Barcode <input name="barcode" placeholder="789..." ${disabled} /></label>
      <label>Text <input name="phrase" placeholder="iogurte batavo" ${disabled} /></label>
      <button type="submit" ${disabled}>Search sources</button>
      ${candidates ? `<ul class="lookup-list">${candidates}</ul>` : ""}
    </form>
  `;
}

function renderManualLog(): string {
  const filtered = filteredFoods();
  const disabled = state.person && filtered.length ? "" : "disabled";
  const quickDisabled = state.household && state.person ? "" : "disabled";
  const options = filtered
    .map((item) => `<option value="${item.version.id}">${escapeHtml(foodOptionLabel(item))}</option>`)
    .join("");
  return `
    <form id="manual-log-form" class="panel">
      <p class="eyebrow">Manual log</p>
      <h2>Diary entry</h2>
      <label>Find food <input class="food-filter" data-filter-id="manual" type="search" value="${escapeHtml(state.foodFilter)}" placeholder="name, brand, alias, barcode" ${state.person && state.foods.length ? "" : "disabled"} /></label>
      <label>Food <select name="food_version_id" ${disabled}>${options}</select></label>
      ${!filtered.length && state.foods.length ? `<p class="hint">No saved foods match this filter.</p>` : ""}
      <label>Time <input name="logged_at_local" type="datetime-local" value="${defaultDateTime("10:00")}" ${disabled} /></label>
      <div class="grid-two">
        <label>Quantity <input name="quantity" type="number" step="0.1" value="100" ${disabled} /></label>
        <label>Unit
          <select name="quantity_unit" ${disabled}>
            <option value="g">Grams</option>
            <option value="serving">Servings</option>
          </select>
        </label>
      </div>
      <button type="submit" ${disabled}>Add entry</button>
    </form>
    <form id="quick-custom-log-form" class="panel">
      <p class="eyebrow">Quick custom</p>
      <h2>New food entry</h2>
      <label>Name <input name="name" value="Pao de queijo caseiro" ${quickDisabled} /></label>
      <label>Brand <input name="brand" placeholder="optional" ${quickDisabled} /></label>
      <div class="grid-two">
        <label>Time <input name="logged_at_local" type="datetime-local" value="${defaultDateTime("16:00")}" ${quickDisabled} /></label>
        <label>Quantity <input name="quantity_g" type="number" step="0.1" value="80" ${quickDisabled} /></label>
        <label>Meal
          <select name="meal_type" ${quickDisabled}>
            ${mealOptions("snack")}
          </select>
        </label>
        <label>Serving g <input name="serving_size_g" type="number" step="0.1" placeholder="optional" ${quickDisabled} /></label>
      </div>
      <div class="grid-two">
        <label>Calories / 100g <input name="calories_kcal" type="number" step="0.1" value="280" ${quickDisabled} /></label>
        <label>Protein / 100g <input name="protein_g" type="number" step="0.1" value="7" ${quickDisabled} /></label>
        <label>Carbs / 100g <input name="carbs_g" type="number" step="0.1" value="35" ${quickDisabled} /></label>
        <label>Fat / 100g <input name="fat_g" type="number" step="0.1" value="12" ${quickDisabled} /></label>
        <label>Fiber / 100g <input name="fiber_g" type="number" step="0.1" value="0" ${quickDisabled} /></label>
        <label>Sodium mg / 100g <input name="sodium_mg" type="number" step="0.1" value="0" ${quickDisabled} /></label>
      </div>
      <label>Aliases <input name="aliases" value="pao de queijo" ${quickDisabled} /></label>
      <label>Barcode <input name="barcode" placeholder="optional" ${quickDisabled} /></label>
      <button type="submit" ${quickDisabled}>Create and log</button>
    </form>
  `;
}

function renderWeightForm(): string {
  const disabled = state.person ? "" : "disabled";
  return `
    <form id="weight-form" class="panel">
      <p class="eyebrow">Weight</p>
      <h2>Reading</h2>
      <label>Time <input name="measured_at_local" type="datetime-local" value="${defaultDateTime("08:00")}" ${disabled} /></label>
      <label>Weight kg <input name="weight_kg" type="number" step="0.1" value="91.2" ${disabled} /></label>
      <label>Note <input name="note" placeholder="optional" ${disabled} /></label>
      <button type="submit" ${disabled}>Add weight</button>
    </form>
  `;
}

function renderTemplatePreview(title: string, body: string): string {
  return `
    <section class="template-preview" aria-label="${escapeHtml(title)} template">
      <div>
        <p class="eyebrow">Message template</p>
        <h3>${escapeHtml(title)}</h3>
      </div>
      <pre>${escapeHtml(body)}</pre>
    </section>
  `;
}

function advancedSettings(content: string): string {
  return `
    <details class="advanced-settings">
      <summary>Advanced settings</summary>
      <div class="advanced-settings-body">${content}</div>
    </details>
  `;
}

function renderAgentChat(): string {
  const disabled = state.person ? "" : "disabled";
  const response = state.chatResponse;
  const template = `Mode: general_chat
Day: ${state.selectedDay}
Instruction: Answer from app data, troubleshoot a log, or draft corrections/review notes without direct writes.
Message: Why was ${state.selectedDay} high in calories?`;
  return `
    <form id="agent-chat-form" class="panel chat-composer">
      <p class="eyebrow">Starter mode</p>
      <h2>Ask / correct</h2>
      ${renderTemplatePreview("General chat prompt", template)}
      <textarea name="message" ${disabled}>Why was ${state.selectedDay} high in calories?</textarea>
      <label>Attachments
        <input name="attachment" type="file" accept="image/*" capture="environment" multiple ${disabled} />
        <span class="field-hint">Optional. Attach label photos here too; the agent can run OCR when it needs image text.</span>
      </label>
      ${advancedSettings(`
        <div class="grid-two">
          <label>Model profile <input name="model_profile" value="deterministic-local" ${disabled} /></label>
          <label>Effort
            <select name="effort" ${disabled}>
              <option value="low">Low</option>
              <option value="medium" selected>Medium</option>
              <option value="high">High</option>
            </select>
          </label>
          <label>Max loops <input name="max_tool_loops" type="number" value="4" min="1" max="12" ${disabled} /></label>
        </div>
        <label class="check-row"><input name="research_lookup" type="checkbox" checked ${disabled} /> Research lookup</label>
        <label class="check-row"><input name="background_job" type="checkbox" ${disabled} /> Run in background</label>
      `)}
      <button type="submit" ${disabled}>Send</button>
      ${
        response
          ? `<section class="chat-answer">
              <strong>${escapeHtml(response.behavior_label)}</strong>
              <p>${escapeHtml(response.message)}</p>
              <span>${response.citations.length} citation${response.citations.length === 1 ? "" : "s"}</span>
            </section>`
          : ""
      }
      ${renderChatHistory()}
    </form>
  `;
}

function renderChatHistory(): string {
  const rows = state.chatHistory
    .slice(-5)
    .reverse()
    .map(
      (turn) => `
        <li>
          <strong>${escapeHtml(turn.user_message)}</strong>
          <p>${escapeHtml(turn.assistant_message)}</p>
          <span>${escapeHtml(turn.behavior_label)} · ${turn.citations.length} citation${turn.citations.length === 1 ? "" : "s"} · ${escapeHtml(formatDateTime(turn.created_at))}</span>
        </li>
      `
    )
    .join("");
  return rows
    ? `<section class="chat-history" aria-label="Agent chat history"><h3>Recent chat</h3><ol>${rows}</ol></section>`
    : "";
}

function renderDataPortability(): string {
  return `
    <form id="import-form" class="panel">
      <p class="eyebrow">Data</p>
      <h2>Export / import</h2>
      <button id="export-data" type="button" ${state.household ? "" : "disabled"}>Export JSON</button>
      <textarea name="import_json" placeholder="Paste exported JSON here">${escapeHtml(state.exportText)}</textarea>
      <button type="submit">Import into empty app</button>
    </form>
  `;
}

function bindEvents(): void {
  document.querySelector<HTMLFormElement>("#setup-form")?.addEventListener("submit", safeAsync(onSetup));
  document.querySelector<HTMLFormElement>("#add-person-form")?.addEventListener("submit", safeAsync(onAddPerson));
  document.querySelector<HTMLFormElement>("#goal-form")?.addEventListener("submit", safeAsync(onGoal));
  document.querySelector<HTMLFormElement>("#food-form")?.addEventListener("submit", safeAsync(onFood));
  document.querySelector<HTMLFormElement>("#food-lookup-form")?.addEventListener("submit", safeAsync(onFoodLookup));
  document.querySelector<HTMLFormElement>("#manual-log-form")?.addEventListener("submit", safeAsync(onManualLog));
  document.querySelector<HTMLFormElement>("#quick-custom-log-form")?.addEventListener("submit", safeAsync(onQuickCustomLog));
  document.querySelector<HTMLFormElement>("#weight-form")?.addEventListener("submit", safeAsync(onWeight));
  document.querySelector<HTMLFormElement>("#text-meal-form")?.addEventListener("submit", safeAsync(onTextMeal));
  document.querySelector<HTMLFormElement>("#agent-chat-form")?.addEventListener("submit", safeAsync(onAgentChat));
  document.querySelector<HTMLFormElement>("#label-scan-form")?.addEventListener("submit", safeAsync(onLabelScan));
  document.querySelector<HTMLFormElement>("#recipe-form")?.addEventListener("submit", safeAsync(onRecipe));
  document
    .querySelector<HTMLButtonElement>("#barcode-scan-start")
    ?.addEventListener("click", safeAsync(onBarcodeScanStart));
  document
    .querySelector<HTMLButtonElement>("#barcode-scan-stop")
    ?.addEventListener("click", safeAsync(onBarcodeScanStop));
  document.querySelector<HTMLFormElement>("#import-form")?.addEventListener("submit", safeAsync(onImportData));
  document
    .querySelectorAll<HTMLSelectElement>(".profile-select")
    .forEach((select) => select.addEventListener("change", safeAsync(onProfileSelect)));
  document
    .querySelectorAll<HTMLInputElement>(".food-filter")
    .forEach((input) => input.addEventListener("input", onFoodFilterInput));
  const logAgentChat = document.querySelector<AgentChatElement>("#log-agent-chat");
  if (logAgentChat) {
    logAgentChat.data = logAgentState();
    logAgentChat.addEventListener("agent-chat:mode-change", onLogAgentModeChange);
    logAgentChat.addEventListener("agent-chat:send", safeAsync(onLogAgentSend));
    logAgentChat.addEventListener("agent-chat:confirm-draft", safeAsync(confirmProposal));
    logAgentChat.addEventListener("agent-chat:reject-draft", safeAsync(rejectProposal));
    logAgentChat.addEventListener("agent-chat:inspect-prompt", onLogAgentInspectPrompt);
    logAgentChat.addEventListener("agent-chat:retry", safeAsync(onReplayOfflineOutbox));
  }
  document.querySelector<HTMLInputElement>("#selected-day")?.addEventListener("change", safeAsync(onSelectedDayChange));
  document.querySelector<HTMLButtonElement>("#refresh-summary")?.addEventListener("click", safeAsync(refreshSummary));
  document.querySelector<HTMLButtonElement>("#refresh-review")?.addEventListener("click", safeAsync(refreshReview));
  document.querySelector<HTMLButtonElement>("#refresh-proposals")?.addEventListener("click", safeAsync(refreshProposals));
  document.querySelector<HTMLButtonElement>("#refresh-jobs")?.addEventListener("click", safeAsync(refreshJobs));
  document
    .querySelector<HTMLButtonElement>("#replay-offline-outbox")
    ?.addEventListener("click", safeAsync(onReplayOfflineOutbox));
  document.querySelector<HTMLButtonElement>("#export-data")?.addEventListener("click", safeAsync(onExportData));
  document.querySelector<HTMLButtonElement>("#confirm-proposal")?.addEventListener("click", safeAsync(confirmProposal));
  document.querySelector<HTMLButtonElement>("#reject-proposal")?.addEventListener("click", safeAsync(rejectProposal));
  document.querySelector<HTMLButtonElement>("#undo-delete")?.addEventListener("click", safeAsync(undoLastDelete));
  document
    .querySelectorAll<HTMLFormElement>(".entry-edit-form")
    .forEach((form) => form.addEventListener("submit", safeAsync(onEntryEdit)));
  document
    .querySelectorAll<HTMLFormElement>(".proposal-entry-edit-form")
    .forEach((form) => form.addEventListener("submit", safeAsync(onProposalEntryEdit)));
  document
    .querySelectorAll<HTMLButtonElement>(".entry-delete")
    .forEach((button) => button.addEventListener("click", safeAsync(onEntryDelete)));
  document
    .querySelectorAll<HTMLButtonElement>(".food-archive")
    .forEach((button) => button.addEventListener("click", safeAsync(onFoodArchive)));
  document
    .querySelectorAll<HTMLFormElement>(".weight-edit-form")
    .forEach((form) => form.addEventListener("submit", safeAsync(onWeightEdit)));
  document
    .querySelectorAll<HTMLButtonElement>(".lookup-propose")
    .forEach((button) => button.addEventListener("click", safeAsync(onLookupPropose)));
  document
    .querySelectorAll<HTMLButtonElement>(".clarification-candidate")
    .forEach((button) => button.addEventListener("click", safeAsync(onClarificationCandidate)));
  document
    .querySelectorAll<HTMLButtonElement>(".job-process")
    .forEach((button) => button.addEventListener("click", safeAsync(onJobProcess)));
  document
    .querySelectorAll<HTMLButtonElement>(".job-load-proposal")
    .forEach((button) => button.addEventListener("click", safeAsync(onJobLoadProposal)));
  document
    .querySelectorAll<HTMLButtonElement>(".job-open-chat")
    .forEach((button) => button.addEventListener("click", safeAsync(onJobOpenChat)));
  document
    .querySelectorAll<HTMLButtonElement>(".offline-retry")
    .forEach((button) => button.addEventListener("click", safeAsync(onOfflineRetry)));
  document
    .querySelectorAll<HTMLButtonElement>(".offline-delete")
    .forEach((button) => button.addEventListener("click", safeAsync(onOfflineDelete)));
  document
    .querySelectorAll<HTMLButtonElement>(".proposal-load-related")
    .forEach((button) => button.addEventListener("click", safeAsync(onRelatedProposalLoad)));
  document
    .querySelectorAll<HTMLButtonElement>(".proposal-open")
    .forEach((button) => button.addEventListener("click", safeAsync(onProposalOpen)));
}

function onLogAgentModeChange(event: Event): void {
  const mode = (event as CustomEvent<{ modeId?: string }>).detail.modeId as LogMode | undefined;
  if (!mode || !logAgentModes().some((candidate) => candidate.id === mode)) return;
  stopBarcodeScanner();
  state.logMode = mode;
  render();
}

function onLogAgentInspectPrompt(): void {
  const mode = logAgentModes().find((candidate) => candidate.id === state.logMode);
  state.notice = mode
    ? `${mode.label} mode prepares a model-visible message while durable writes stay reviewable.`
    : "The chat surface prepares messages for the agent without applying durable writes directly.";
  render();
}

async function onBarcodeScanStart(): Promise<void> {
  const detectorCtor = (
    window as Window & {
      BarcodeDetector?: new (options?: { formats?: string[] }) => BrowserBarcodeDetector;
    }
  ).BarcodeDetector;
  if (!detectorCtor) {
    state.notice = "This browser cannot decode barcodes directly. Use the photo upload or type the numbers.";
    render();
    return;
  }
  const scanner = document.querySelector<HTMLElement>("#barcode-scanner");
  const video = document.querySelector<HTMLVideoElement>("#barcode-video");
  const input = document.querySelector<HTMLInputElement>("#label-scan-form input[name='barcode']");
  if (!scanner || !video || !input) return;
  stopBarcodeScanner();
  barcodeScannerStream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: { ideal: "environment" } },
    audio: false
  });
  video.srcObject = barcodeScannerStream;
  scanner.hidden = false;
  await video.play();
  const detector = new detectorCtor({
    formats: ["ean_13", "ean_8", "upc_a", "upc_e", "code_128"]
  });
  barcodeScannerTimer = window.setInterval(() => {
    void (async () => {
      if (!barcodeScannerStream || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return;
      const results = await detector.detect(video);
      const value = results[0]?.rawValue?.trim();
      if (!value) return;
      input.value = value;
      stopBarcodeScanner();
      state.notice = "Barcode scanned.";
      render();
    })().catch((error) => {
      stopBarcodeScanner();
      reportUiError(error);
    });
  }, 450);
}

async function onBarcodeScanStop(): Promise<void> {
  stopBarcodeScanner();
  state.notice = "Barcode camera stopped.";
  render();
}

function stopBarcodeScanner(): void {
  if (barcodeScannerTimer !== null) {
    window.clearInterval(barcodeScannerTimer);
    barcodeScannerTimer = null;
  }
  if (barcodeScannerStream) {
    barcodeScannerStream.getTracks().forEach((track) => track.stop());
    barcodeScannerStream = null;
  }
  const scanner = document.querySelector<HTMLElement>("#barcode-scanner");
  const video = document.querySelector<HTMLVideoElement>("#barcode-video");
  if (video) video.srcObject = null;
  if (scanner) scanner.hidden = true;
}

function safeAsync<T extends Event>(handler: (event: T) => Promise<void>): (event: T) => void {
  return (event: T) => {
    void (async () => {
      const hadError = state.errorMessage !== null;
      state.errorMessage = null;
      try {
        await handler(event);
        if (hadError && state.errorMessage === null) {
          render();
        }
      } catch (error) {
        reportUiError(error);
      }
    })();
  };
}

function reportUiError(error: unknown): void {
  state.errorMessage = error instanceof Error ? error.message : "Something went wrong.";
  state.notice = null;
  render();
}

async function loadOfflineOutbox(): Promise<void> {
  state.offlineOutbox = await offlineOutboxAll();
  render();
  if (navigator.onLine) {
    await replayOfflineOutbox();
  }
}

async function onReplayOfflineOutbox(): Promise<void> {
  await replayOfflineOutbox();
}

async function onOfflineRetry(event: Event): Promise<void> {
  const id = (event.currentTarget as HTMLButtonElement).dataset.outboxId;
  if (!id) return;
  const item = state.offlineOutbox.find((candidate) => candidate.id === id);
  if (!item) return;
  await saveOfflineOutboxItem({ ...item, status: "pending", last_error: null });
  await loadOfflineOutbox();
  await replayOfflineOutbox();
}

async function onOfflineDelete(event: Event): Promise<void> {
  const id = (event.currentTarget as HTMLButtonElement).dataset.outboxId;
  if (!id) return;
  await deleteOfflineOutboxItem(id);
  state.offlineOutbox = state.offlineOutbox.filter((item) => item.id !== id);
  state.notice = "Offline note deleted.";
  render();
}

async function queueOfflineAgent(
  kind: OfflineOutboxKind,
  payload: Record<string, unknown>,
  files: OfflineOutboxFile[] = [],
  error: unknown = null
): Promise<void> {
  if (!state.person) return;
  const requestId = newClientRequestId();
  const item: OfflineOutboxItem = {
    id: requestId,
    client_request_id: requestId,
    kind,
    household_id: state.household?.id ?? null,
    person_id: state.person.id,
    selected_day: state.selectedDay,
    payload,
    files,
    status: "pending",
    attempts: 0,
    last_error: error instanceof Error ? error.message : null,
    created_at: new Date().toISOString(),
    replayed_at: null
  };
  await saveOfflineOutboxItem(item);
  state.offlineOutbox = await offlineOutboxAll();
  state.notice = `${jobLabel(kind)} saved offline. It will queue for the worker when reconnected.`;
  render();
}

async function replayOfflineOutbox(): Promise<void> {
  if (state.isOfflineReplayRunning || !navigator.onLine) {
    if (!navigator.onLine) {
      state.notice = "Waiting for connection before replaying offline notes.";
      render();
    }
    return;
  }
  const candidates = (await offlineOutboxAll()).filter(
    (item) => item.status === "pending" || item.status === "failed"
  );
  if (!candidates.length) {
    state.offlineOutbox = await offlineOutboxAll();
    render();
    return;
  }
  state.isOfflineReplayRunning = true;
  state.offlineOutbox = await offlineOutboxAll();
  render();
  for (const item of candidates) {
    let current: OfflineOutboxItem = {
      ...item,
      status: "replaying",
      attempts: item.attempts + 1,
      last_error: null
    };
    await saveOfflineOutboxItem(current);
    state.offlineOutbox = await offlineOutboxAll();
    render();
    try {
      const payload = { ...current.payload };
      const existingAttachmentIds = Array.isArray(payload.attachment_ids)
        ? payload.attachment_ids
        : [];
      if (!existingAttachmentIds.length && current.files.length) {
        const attachments: AttachmentObject[] = [];
        for (const file of current.files) {
          attachments.push(await uploadQueuedAttachment(current, file));
        }
        payload.attachment_ids = attachments.map((attachment) => attachment.id);
        payload.attachment_id = attachments[0]?.id ?? null;
        if (current.kind === "agent_chat") {
          payload.message = appendAttachmentIdsToMessage(
            String(payload.message ?? ""),
            payload.attachment_ids as string[]
          );
        }
      }
      const job = await apiPost<BackgroundJob>("/api/jobs", {
        job_type: current.kind,
        payload,
        client_request_id: current.client_request_id
      });
      replaceJob(job);
      current = {
        ...current,
        payload,
        status: "sent",
        last_error: null,
        replayed_at: new Date().toISOString()
      };
      await saveOfflineOutboxItem(current);
    } catch (error) {
      current = {
        ...current,
        status: "failed",
        last_error: error instanceof Error ? error.message : "Replay failed"
      };
      await saveOfflineOutboxItem(current);
      if (isProbablyOfflineError(error)) {
        break;
      }
    }
  }
  state.isOfflineReplayRunning = false;
  state.offlineOutbox = await offlineOutboxAll();
  state.notice = state.offlineOutbox.some((item) => item.status === "failed")
    ? "Some offline notes still need retry."
    : "Offline notes replayed to the worker queue.";
  await refreshJobsIfPossible();
  render();
}

async function uploadQueuedAttachment(
  item: OfflineOutboxItem,
  queuedFile: OfflineOutboxFile
): Promise<AttachmentObject> {
  if (!item.household_id) {
    throw new Error("Queued upload is missing household context.");
  }
  return apiPost<AttachmentObject>("/api/attachments", {
    household_id: item.household_id,
    person_id: item.person_id,
    object_type: queuedFile.object_type,
    mime_type: queuedFile.mime_type || "application/octet-stream",
    filename: queuedFile.filename,
    content_base64: await blobToBase64(queuedFile.blob),
    retention_policy: "keep"
  });
}

async function refreshJobsIfPossible(): Promise<void> {
  if (!state.person) return;
  try {
    await refreshJobs();
  } catch {
    // Keep replay status visible even if the jobs list cannot refresh yet.
  }
}

function isProbablyOfflineError(error: unknown): boolean {
  return !navigator.onLine || error instanceof TypeError;
}

function newClientRequestId(): string {
  return `offline_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function openOutboxDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (!("indexedDB" in window)) {
      reject(new Error("IndexedDB is unavailable in this browser."));
      return;
    }
    const request = indexedDB.open(outboxDbName, 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(outboxStoreName)) {
        db.createObjectStore(outboxStoreName, { keyPath: "id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("Failed to open offline outbox."));
  });
}

async function withOutboxStore<T>(
  mode: IDBTransactionMode,
  operation: (store: IDBObjectStore) => IDBRequest<T>
): Promise<T> {
  const db = await openOutboxDb();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(outboxStoreName, mode);
    const request = operation(transaction.objectStore(outboxStoreName));
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("Offline outbox operation failed."));
    transaction.oncomplete = () => db.close();
    transaction.onerror = () => {
      db.close();
      reject(transaction.error ?? new Error("Offline outbox transaction failed."));
    };
  });
}

async function offlineOutboxAll(): Promise<OfflineOutboxItem[]> {
  return withOutboxStore<OfflineOutboxItem[]>("readonly", (store) => store.getAll());
}

async function saveOfflineOutboxItem(item: OfflineOutboxItem): Promise<void> {
  await withOutboxStore<IDBValidKey>("readwrite", (store) => store.put(item));
}

async function deleteOfflineOutboxItem(id: string): Promise<void> {
  await withOutboxStore<undefined>("readwrite", (store) => store.delete(id));
}

async function onSetup(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  const form = new FormData(event.currentTarget as HTMLFormElement);
  const household = await apiPost<Household>("/api/households", { name: requiredText(form, "household") });
  const person = await apiPost<Person>("/api/people", {
    household_id: household.id,
    name: requiredText(form, "name"),
    timezone: requiredText(form, "timezone"),
    birth_date: optionalText(form, "birth_date"),
    sex: optionalText(form, "sex"),
    height_cm: optionalNumber(form, "height_cm"),
    activity_level: optionalText(form, "activity_level")
  });
  const goal = await createGoalFromFields(person.id, {
    starts_on: state.selectedDay,
    calories_kcal: numberField(form, "target_calories_kcal"),
    protein_g: numberField(form, "target_protein_g"),
    carbs_g: numberField(form, "target_carbs_g"),
    fat_g: numberField(form, "target_fat_g"),
    fiber_g: numberField(form, "target_fiber_g"),
    sodium_mg: numberField(form, "target_sodium_mg"),
    notes: "initial plan"
  });
  state.household = household;
  state.people = [person];
  state.person = person;
  state.activeGoal = goal;
  saveSession();
  state.notice = "Profile created.";
  await refreshAllReadSurfaces();
}

async function onAddPerson(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.household) return;
  const form = new FormData(event.currentTarget as HTMLFormElement);
  const person = await apiPost<Person>("/api/people", {
    household_id: state.household.id,
    name: requiredText(form, "name"),
    timezone: requiredText(form, "timezone"),
    birth_date: optionalText(form, "birth_date"),
    sex: optionalText(form, "sex"),
    height_cm: optionalNumber(form, "height_cm"),
    activity_level: optionalText(form, "activity_level")
  });
  state.people = [...state.people, person];
  state.person = person;
  clearPersonScopedState();
  saveSession();
  state.notice = `${person.name} added.`;
  await refreshAllReadSurfaces();
}

async function onProfileSelect(event: Event): Promise<void> {
  const selectedId = (event.currentTarget as HTMLSelectElement).value;
  const selected = state.people.find((person) => person.id === selectedId);
  if (!selected) return;
  state.person = selected;
  clearPersonScopedState();
  saveSession();
  state.notice = `Switched to ${selected.name}.`;
  await refreshAllReadSurfaces();
}

async function onSelectedDayChange(event: Event): Promise<void> {
  const selectedDay = (event.currentTarget as HTMLInputElement).value;
  if (!selectedDay || selectedDay === state.selectedDay) return;
  state.selectedDay = selectedDay;
  state.summary = null;
  state.week = null;
  state.proposal = null;
  state.chatResponse = null;
  state.lastDeletedEntry = null;
  saveSession();
  state.notice = `Showing ${selectedDay}.`;
  await refreshAllReadSurfaces();
}

function onFoodFilterInput(event: Event): void {
  const input = event.currentTarget as HTMLInputElement;
  const filterId = input.dataset.filterId ?? "";
  const cursor = input.selectionStart ?? input.value.length;
  state.foodFilter = input.value;
  render();
  const nextInput = document.querySelector<HTMLInputElement>(
    `.food-filter[data-filter-id="${filterId}"]`
  );
  nextInput?.focus();
  nextInput?.setSelectionRange(cursor, cursor);
}

async function onGoal(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.person) return;
  const form = new FormData(event.currentTarget as HTMLFormElement);
  state.activeGoal = await createGoalFromFields(state.person.id, {
    starts_on: requiredText(form, "starts_on"),
    calories_kcal: numberField(form, "calories_kcal"),
    protein_g: numberField(form, "protein_g"),
    carbs_g: numberField(form, "carbs_g"),
    fat_g: numberField(form, "fat_g"),
    fiber_g: numberField(form, "goal_fiber_g"),
    sodium_mg: numberField(form, "goal_sodium_mg"),
    notes: optionalText(form, "notes")
  });
  state.notice = "Targets saved.";
  await refreshAllReadSurfaces();
}

async function onEntryEdit(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  const formElement = event.currentTarget as HTMLFormElement;
  const entryId = formElement.dataset.entryId;
  if (!entryId) return;
  const form = new FormData(formElement);
  await apiPatch<DiaryEntryRecord>(`/api/diary/${entryId}`, {
    quantity_g: numberField(form, "quantity_g"),
    meal_type: requiredText(form, "meal_type")
  });
  state.lastDeletedEntry = null;
  state.notice = "Diary entry updated.";
  await refreshAllReadSurfaces();
}

async function onProposalEntryEdit(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.proposal) return;
  const formElement = event.currentTarget as HTMLFormElement;
  const entryId = formElement.dataset.entryId;
  if (!entryId) return;
  const form = new FormData(formElement);
  state.proposal = await apiPatch<Proposal>(`/api/proposals/${state.proposal.id}/entries/${entryId}`, {
    food_version_id: requiredText(form, "food_version_id"),
    quantity_g: numberField(form, "quantity_g"),
    meal_type: requiredText(form, "meal_type")
  });
  state.notice = "Proposal entry updated.";
  await refreshProposals();
}

async function onEntryDelete(event: Event): Promise<void> {
  const entryId = (event.currentTarget as HTMLButtonElement).dataset.entryId;
  if (!entryId) return;
  state.lastDeletedEntry = await apiDelete<DiaryEntryRecord>(`/api/diary/${entryId}`);
  state.notice = "Diary entry deleted.";
  await refreshAllReadSurfaces();
}

async function undoLastDelete(): Promise<void> {
  if (!state.lastDeletedEntry) return;
  const restored = await apiPost<DiaryEntryRecord>(
    `/api/diary/${state.lastDeletedEntry.id}/restore`,
    {}
  );
  state.lastDeletedEntry = null;
  state.notice = `Restored ${restored.quantity_g} g entry.`;
  await refreshAllReadSurfaces();
}

async function onFood(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.household) return;
  const form = new FormData(event.currentTarget as HTMLFormElement);
  const food = await apiPost<FoodResponse>("/api/foods", {
    household_id: state.household.id,
    name: requiredText(form, "name"),
    brand: optionalText(form, "brand"),
    version_label: requiredText(form, "version_label"),
    source: "label_scan",
    nutrients_per_100g: {
      calories_kcal: numberField(form, "calories_kcal"),
      protein_g: numberField(form, "protein_g"),
      carbs_g: numberField(form, "carbs_g"),
      fat_g: numberField(form, "fat_g"),
      fiber_g: numberField(form, "fiber_g"),
      sodium_mg: numberField(form, "sodium_mg")
    },
    aliases: optionalText(form, "aliases")
      ?.split(",")
      .map((alias) => alias.trim())
      .filter(Boolean),
    barcode: optionalText(form, "barcode"),
    serving_size_g: optionalNumber(form, "serving_size_g")
  });
  state.foods = [...state.foods, food];
  state.notice = `${foodLabel(food)} saved.`;
  render();
}

async function onFoodLookup(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.household || !state.person) return;
  const form = new FormData(event.currentTarget as HTMLFormElement);
  const params = new URLSearchParams({
    household_id: state.household.id,
    person_id: state.person.id
  });
  const barcode = optionalText(form, "barcode");
  const phrase = optionalText(form, "phrase");
  if (barcode) params.set("barcode", barcode);
  if (phrase) params.set("phrase", phrase);
  state.lookupCandidates = await apiGet<FoodLookupCandidate[]>(`/api/lookups/foods?${params.toString()}`);
  state.notice = `${state.lookupCandidates.length} lookup candidate${state.lookupCandidates.length === 1 ? "" : "s"} found.`;
  render();
}

async function onFoodArchive(event: Event): Promise<void> {
  const foodId = (event.currentTarget as HTMLButtonElement).dataset.foodId;
  if (!foodId) return;
  if (!window.confirm("Archive this food for future logging? Historical diary entries stay unchanged.")) {
    return;
  }
  await apiPost<Food>(`/api/foods/${foodId}/archive`, {});
  state.notice = "Food archived. Historical diary entries are unchanged.";
  await refreshFoodLibrary();
  render();
}

async function onLookupPropose(event: Event): Promise<void> {
  if (!state.household || !state.person) return;
  const candidateId = (event.currentTarget as HTMLButtonElement).dataset.candidateId;
  if (!candidateId) return;
  state.proposal = await apiPost<Proposal>("/api/lookups/foods/propose", {
    household_id: state.household.id,
    person_id: state.person.id,
    candidate_id: candidateId
  });
  state.notice = "Lookup proposal drafted.";
  await refreshProposals();
}

async function onClarificationCandidate(event: Event): Promise<void> {
  if (!state.proposal) return;
  const button = event.currentTarget as HTMLButtonElement;
  const unresolvedIndex = Number(button.dataset.unresolvedIndex);
  const foodVersionId = button.dataset.foodVersionId;
  if (!foodVersionId || Number.isNaN(unresolvedIndex)) return;
  state.proposal = await apiPost<Proposal>(`/api/proposals/${state.proposal.id}/resolve-food`, {
    unresolved_index: unresolvedIndex,
    food_version_id: foodVersionId
  });
  state.notice = "Clarification resolved. Review before applying.";
  await refreshProposals();
}

async function onJobProcess(event: Event): Promise<void> {
  const jobId = (event.currentTarget as HTMLButtonElement).dataset.jobId;
  if (!jobId) return;
  const job = await apiPost<BackgroundJob>(`/api/jobs/${jobId}/process`, {});
  replaceJob(job);
  await adoptJobProposal(job);
  await adoptJobChat(job);
  state.notice = `Job ${job.status}.`;
  await refreshProposals();
  render();
}

async function onJobLoadProposal(event: Event): Promise<void> {
  const proposalId = (event.currentTarget as HTMLButtonElement).dataset.proposalId;
  if (!proposalId) return;
  await loadProposal(proposalId, "Loaded job proposal. Review before applying.");
}

async function onJobOpenChat(event: Event): Promise<void> {
  const chatTurnId = (event.currentTarget as HTMLButtonElement).dataset.chatTurnId;
  if (!chatTurnId) return;
  await openChatTurn(chatTurnId, "Loaded job chat answer.");
  render();
}

async function onRelatedProposalLoad(event: Event): Promise<void> {
  const proposalId = (event.currentTarget as HTMLButtonElement).dataset.proposalId;
  if (!proposalId) return;
  await loadProposal(proposalId, "Loaded related proposal.");
}

async function onProposalOpen(event: Event): Promise<void> {
  const proposalId = (event.currentTarget as HTMLButtonElement).dataset.proposalId;
  if (!proposalId) return;
  await loadProposal(proposalId, "Loaded proposal from inbox.");
}

async function loadProposal(proposalId: string, notice: string): Promise<void> {
  state.proposal = await apiGet<Proposal>(`/api/proposals/${proposalId}`);
  state.notice = notice;
  render();
}

async function onManualLog(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.person) return;
  const form = new FormData(event.currentTarget as HTMLFormElement);
  const quantityUnit = requiredText(form, "quantity_unit");
  const quantity = numberField(form, "quantity");
  await apiPost("/api/diary", {
    person_id: state.person.id,
    logged_at_local: requiredText(form, "logged_at_local"),
    food_version_id: requiredText(form, "food_version_id"),
    ...(quantityUnit === "serving" ? { serving_count: quantity } : { quantity_g: quantity }),
    source: "manual"
  });
  state.notice = "Diary entry added.";
  await refreshAllReadSurfaces();
}

async function onQuickCustomLog(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.household || !state.person) return;
  const form = new FormData(event.currentTarget as HTMLFormElement);
  const created = await apiPost<QuickCustomFoodResponse>("/api/diary/custom-food", {
    household_id: state.household.id,
    person_id: state.person.id,
    name: requiredText(form, "name"),
    brand: optionalText(form, "brand"),
    version_label: "quick custom",
    nutrients_per_100g: {
      calories_kcal: numberField(form, "calories_kcal"),
      protein_g: numberField(form, "protein_g"),
      carbs_g: numberField(form, "carbs_g"),
      fat_g: numberField(form, "fat_g"),
      fiber_g: numberField(form, "fiber_g"),
      sodium_mg: numberField(form, "sodium_mg")
    },
    logged_at_local: requiredText(form, "logged_at_local"),
    quantity_g: numberField(form, "quantity_g"),
    aliases: optionalText(form, "aliases")
      ?.split(",")
      .map((alias) => alias.trim())
      .filter(Boolean),
    serving_size_g: optionalNumber(form, "serving_size_g"),
    barcode: optionalText(form, "barcode"),
    meal_type: requiredText(form, "meal_type")
  });
  state.foods = [...state.foods, created];
  state.notice = `${foodLabel(created)} created and logged.`;
  await refreshAllReadSurfaces();
}

async function onWeight(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.person) return;
  const form = new FormData(event.currentTarget as HTMLFormElement);
  await apiPost("/api/weights", {
    person_id: state.person.id,
    measured_at_local: requiredText(form, "measured_at_local"),
    weight_kg: numberField(form, "weight_kg"),
    note: optionalText(form, "note"),
    source: "manual"
  });
  state.notice = "Weight added.";
  await refreshReview();
}

async function onWeightEdit(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  const formElement = event.currentTarget as HTMLFormElement;
  const weightId = formElement.dataset.weightId;
  if (!weightId) return;
  const form = new FormData(formElement);
  await apiPatch<WeightEntry>(`/api/weights/${weightId}`, {
    measured_at_local: requiredText(form, "measured_at_local"),
    weight_kg: numberField(form, "weight_kg"),
    note: optionalText(form, "note")
  });
  state.notice = "Weight updated.";
  await refreshReview();
}

function recordLogEvent(mode: LogMode, title: string, message: string, result: string): void {
  state.logEvents = [
    ...state.logEvents.slice(-7),
    {
      id: newClientRequestId(),
      mode,
      title,
      message,
      result,
      created_at: new Date().toISOString()
    }
  ];
}

function textMealPromptPreview(payload: {
  logged_at_local: string;
  text: string;
  agent_settings: Record<string, unknown>;
}): string {
  return `Mode: meal_log
Day: ${state.selectedDay}
Logged at: ${payload.logged_at_local}
Settings: ${JSON.stringify(payload.agent_settings)}
User note: ${payload.text}`;
}

function chatPromptPreview(payload: {
  today: string;
  message: string;
  attachment_ids?: string[];
  agent_settings: Record<string, unknown>;
}): string {
  return `Mode: general_chat
Day: ${payload.today}
Settings: ${JSON.stringify(payload.agent_settings)}
Attachments: ${payload.attachment_ids?.length ? payload.attachment_ids.join(", ") : "none"}
Message: ${payload.message}`;
}

function appendAttachmentIdsToMessage(message: string, attachmentIds: string[]): string {
  if (!attachmentIds.length) return message;
  return `${message.trim()}

Attached image ids for OCR:
${attachmentIds.map((id) => `- ${id}`).join("\n")}`;
}

function labelScanPromptPreview(payload: {
  table_text: string;
  barcode: string | null;
  attachment_id: string | null;
  attachment_ids?: string[];
  logged_at_local: string | null;
  quantity_g: number | null;
  meal_type: string | null;
}): string {
  const photoCount = payload.attachment_ids?.length ?? (payload.attachment_id ? 1 : 0);
  return `Mode: label_scan
Barcode: ${payload.barcode ?? "none"}
Photos: ${photoCount ? `${photoCount} uploaded (${payload.attachment_ids?.join(", ") ?? payload.attachment_id})` : "pending or none"}
Optional log: ${payload.quantity_g === null ? "none" : `${payload.quantity_g} g at ${payload.logged_at_local} (${payload.meal_type})`}
Nutrition label:
${payload.table_text || "[image only]"}`;
}

function recipePromptPreview(payload: {
  recipe_text: string;
  logged_at_local: string | null;
  quantity_g: number | null;
  meal_type: string | null;
}): string {
  return `Mode: recipe
Optional log: ${payload.quantity_g === null ? "none" : `${payload.quantity_g} g at ${payload.logged_at_local} (${payload.meal_type})`}
Recipe:
${payload.recipe_text}`;
}

async function onLogAgentSend(event: Event): Promise<void> {
  event.preventDefault();
  const detail = (event as CustomEvent<AgentChatSendPayload>).detail;
  if (!state.person) return;
  if (detail.modeId === "meal") {
    await submitLogAgentMeal(detail);
    return;
  }
  if (detail.modeId === "label") {
    await submitLogAgentLabel(detail);
    return;
  }
  if (detail.modeId === "recipe") {
    await submitLogAgentRecipe(detail);
    return;
  }
  await submitLogAgentChat(detail);
}

async function submitLogAgentMeal(detail: AgentChatSendPayload): Promise<void> {
  if (!state.person) return;
  const payload = {
    person_id: state.person.id,
    logged_at_local: `${state.selectedDay}T10:00:00`,
    text: detail.text,
    agent_settings: {
      model_profile: "ollama-local",
      effort: "medium",
      max_tool_loops: 4,
      external_lookup: true,
      research_lookup: true
    }
  };
  try {
    if (!navigator.onLine) {
      await queueOfflineAgent("agent_text_meal", payload, []);
      recordLogEvent("meal", "Meal note saved offline", textMealPromptPreview(payload), "Saved locally and will replay after reconnect.");
      render();
      return;
    }
    state.proposal = await apiPost<Proposal>("/api/agent/text-meal", payload);
  } catch (error) {
    if (!isProbablyOfflineError(error)) throw error;
    await queueOfflineAgent("agent_text_meal", payload, [], error);
    recordLogEvent("meal", "Meal note saved offline", textMealPromptPreview(payload), "Saved locally and will replay after reconnect.");
    render();
    return;
  }
  recordLogEvent("meal", "Meal note sent", textMealPromptPreview(payload), state.proposal.summary);
  state.notice = "Proposal drafted. Review before applying.";
  await refreshProposals();
}

async function submitLogAgentChat(detail: AgentChatSendPayload): Promise<void> {
  if (!state.person) return;
  const files = queuedFilesFromAgentChat(detail.attachments, "chat_image");
  const payload = {
    person_id: state.person.id,
    message: detail.text,
    today: state.selectedDay,
    attachment_ids: [] as string[],
    agent_settings: {
      model_profile: "deterministic-local",
      effort: "medium",
      max_tool_loops: 4,
      research_lookup: true
    }
  };
  if (!navigator.onLine) {
    await queueOfflineAgent("agent_chat", payload, files);
    recordLogEvent("chat", "Chat saved offline", chatPromptPreview(payload), "Saved locally and will replay after reconnect.");
    render();
    return;
  }
  let uploadedAttachments: AttachmentObject[] = [];
  try {
    uploadedAttachments = await uploadAgentChatAttachments(detail.attachments, "chat_image");
    payload.attachment_ids = uploadedAttachments.map((attachment) => attachment.id);
    if (payload.attachment_ids.length) {
      payload.message = appendAttachmentIdsToMessage(payload.message, payload.attachment_ids);
    }
    await enqueueJob("agent_chat", payload);
  } catch (error) {
    if (!isProbablyOfflineError(error)) throw error;
    await queueOfflineAgent(
      "agent_chat",
      uploadedAttachments.length ? payload : { ...payload, attachment_ids: [] },
      uploadedAttachments.length ? [] : files,
      error
    );
    recordLogEvent("chat", "Chat saved offline", chatPromptPreview(payload), "Saved locally and will replay after reconnect.");
    render();
    return;
  }
  recordLogEvent("chat", "Chat queued", chatPromptPreview(payload), "Background job queued for the worker.");
  render();
}

async function submitLogAgentLabel(detail: AgentChatSendPayload): Promise<void> {
  if (!state.household || !state.person) return;
  const files = queuedFilesFromAgentChat(detail.attachments, "nutrition_label_image");
  const quantityG = extractGrams(detail.text);
  const payload = {
    household_id: state.household.id,
    person_id: state.person.id,
    table_text: detail.text,
    barcode: extractBarcode(detail.text),
    set_as_default: true,
    attachment_id: null as string | null,
    attachment_ids: [] as string[],
    logged_at_local: quantityG === null ? null : `${state.selectedDay}T10:00:00`,
    quantity_g: quantityG,
    meal_type: quantityG === null ? null : "breakfast"
  };
  if (!navigator.onLine) {
    await queueOfflineAgent("agent_label_scan", payload, files);
    recordLogEvent("label", "Product label saved offline", labelScanPromptPreview(payload), "Saved locally with upload evidence for replay.");
    render();
    return;
  }
  let uploadedAttachments: AttachmentObject[] = [];
  try {
    uploadedAttachments = await uploadAgentChatAttachments(detail.attachments, "nutrition_label_image");
    payload.attachment_ids = uploadedAttachments.map((attachment) => attachment.id);
    payload.attachment_id = payload.attachment_ids[0] ?? null;
    state.proposal = await apiPost<Proposal>("/api/agent/label-scan", payload);
  } catch (error) {
    if (!isProbablyOfflineError(error)) throw error;
    await queueOfflineAgent(
      "agent_label_scan",
      uploadedAttachments.length ? payload : { ...payload, attachment_id: null, attachment_ids: [] },
      uploadedAttachments.length ? [] : files,
      error
    );
    recordLogEvent("label", "Product label saved offline", labelScanPromptPreview(payload), "Saved locally with upload evidence for replay.");
    render();
    return;
  }
  recordLogEvent("label", "Product label sent", labelScanPromptPreview(payload), state.proposal.summary);
  state.notice = uploadedAttachments.length
    ? `Food version proposal drafted with ${uploadedAttachments.length} attachment${uploadedAttachments.length === 1 ? "" : "s"}.`
    : "Food version proposal drafted.";
  await refreshProposals();
}

async function submitLogAgentRecipe(detail: AgentChatSendPayload): Promise<void> {
  if (!state.household || !state.person) return;
  const quantityG = extractGrams(detail.text);
  const payload = {
    household_id: state.household.id,
    person_id: state.person.id,
    recipe_text: cleanRecipeText(detail.text),
    logged_at_local: quantityG === null ? null : `${state.selectedDay}T12:30:00`,
    quantity_g: quantityG,
    meal_type: quantityG === null ? null : "lunch"
  };
  try {
    if (!navigator.onLine) {
      await queueOfflineAgent("agent_recipe", payload, []);
      recordLogEvent("recipe", "Recipe saved offline", recipePromptPreview(payload), "Saved locally and will replay after reconnect.");
      render();
      return;
    }
    state.proposal = await apiPost<Proposal>("/api/agent/recipe", payload);
  } catch (error) {
    if (!isProbablyOfflineError(error)) throw error;
    await queueOfflineAgent("agent_recipe", payload, [], error);
    recordLogEvent("recipe", "Recipe saved offline", recipePromptPreview(payload), "Saved locally and will replay after reconnect.");
    render();
    return;
  }
  recordLogEvent("recipe", "Recipe sent", recipePromptPreview(payload), state.proposal.summary);
  state.notice = "Recipe proposal drafted.";
  await refreshProposals();
}

async function uploadAgentChatAttachments(
  attachments: AgentChatAttachment[],
  objectType: string
): Promise<AttachmentObject[]> {
  if (!state.household || !state.person) return [];
  const uploaded: AttachmentObject[] = [];
  for (const attachment of attachments) {
    if (!attachment.file || attachment.file.size <= 0) continue;
    uploaded.push(
      await apiPost<AttachmentObject>("/api/attachments", {
        household_id: state.household.id,
        person_id: state.person.id,
        object_type: objectType,
        mime_type: attachment.file.type || attachment.mimeType || "application/octet-stream",
        filename: attachment.file.name || attachment.name || null,
        content_base64: await fileToBase64(attachment.file),
        retention_policy: "keep"
      })
    );
  }
  return uploaded;
}

function queuedFilesFromAgentChat(
  attachments: AgentChatAttachment[],
  objectType: string
): OfflineOutboxFile[] {
  return attachments
    .filter((attachment): attachment is AgentChatAttachment & { file: File } => !!attachment.file && attachment.file.size > 0)
    .map((attachment) => ({
      field: "attachment",
      object_type: objectType,
      filename: attachment.file.name || attachment.name || null,
      mime_type: attachment.file.type || attachment.mimeType || "application/octet-stream",
      blob: attachment.file
    }));
}

function extractBarcode(text: string): string | null {
  const labeled = text.match(/(?:barcode|codigo|c[oó]digo|ean)\s*[:#-]?\s*(\d{8,14})/i);
  if (labeled?.[1]) return labeled[1];
  return text.match(/\b\d{8,14}\b/)?.[0] ?? null;
}

function extractGrams(text: string): number | null {
  const labeled = text.match(/(?:quantity|log grams|portion|por[cç][aã]o|quantidade)\s*[:#-]?\s*(\d+(?:[.,]\d+)?)\s*g\b/i);
  const generic = text.match(/\b(\d+(?:[.,]\d+)?)\s*g\b/i);
  const raw = labeled?.[1] ?? generic?.[1] ?? null;
  return raw ? Number(raw.replace(",", ".")) : null;
}

function cleanRecipeText(text: string): string {
  return text
    .split("\n")
    .filter((line) => !/^\s*(?:quantity|log grams|portion|por[cç][aã]o|quantidade)\s*[:#-]?\s*\d+(?:[.,]\d+)?\s*g\s*$/i.test(line))
    .join("\n")
    .trim();
}

async function onTextMeal(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.person) return;
  const form = new FormData(event.currentTarget as HTMLFormElement);
  const payload = {
    person_id: state.person.id,
    logged_at_local: `${state.selectedDay}T10:00:00`,
    text: requiredText(form, "text"),
    agent_settings: {
      model_profile: requiredText(form, "model_profile"),
      effort: requiredText(form, "effort"),
      max_tool_loops: numberField(form, "max_tool_loops"),
      external_lookup: form.get("external_lookup") === "on",
      research_lookup: form.get("research_lookup") === "on"
    }
  };
  if (form.get("background_job") === "on") {
    try {
      await enqueueJob("agent_text_meal", payload);
    } catch (error) {
      if (!isProbablyOfflineError(error)) throw error;
      await queueOfflineAgent("agent_text_meal", payload, [], error);
    }
    recordLogEvent("meal", "Meal note queued", textMealPromptPreview(payload), "Background job queued for proposal drafting.");
    render();
    return;
  }
  try {
    state.proposal = await apiPost<Proposal>("/api/agent/text-meal", payload);
  } catch (error) {
    if (!isProbablyOfflineError(error)) throw error;
    await queueOfflineAgent("agent_text_meal", payload, [], error);
    recordLogEvent("meal", "Meal note saved offline", textMealPromptPreview(payload), "Saved locally and will replay after reconnect.");
    render();
    return;
  }
  recordLogEvent("meal", "Meal note sent", textMealPromptPreview(payload), state.proposal.summary);
  state.notice = "Proposal drafted. Review before applying.";
  await refreshProposals();
}

async function onAgentChat(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.person) return;
  const form = new FormData(event.currentTarget as HTMLFormElement);
  const queuedFiles = queuedFilesFromForm(form, "attachment", "chat_image");
  let message = requiredText(form, "message");
  const payload = {
    person_id: state.person.id,
    message,
    today: state.selectedDay,
    attachment_ids: [] as string[],
    agent_settings: {
      model_profile: requiredText(form, "model_profile"),
      effort: requiredText(form, "effort"),
      max_tool_loops: numberField(form, "max_tool_loops"),
      research_lookup: form.get("research_lookup") === "on"
    }
  };
  if (!navigator.onLine) {
    await queueOfflineAgent("agent_chat", payload, queuedFiles);
    recordLogEvent("chat", "Chat saved offline", chatPromptPreview(payload), "Saved locally and will replay after reconnect.");
    render();
    return;
  }
  let attachments: AttachmentObject[] = [];
  try {
    attachments = await uploadOptionalAttachments(form, "attachment", "chat_image");
    payload.attachment_ids = attachments.map((attachment) => attachment.id);
    if (payload.attachment_ids.length) {
      payload.message = appendAttachmentIdsToMessage(message, payload.attachment_ids);
    }
  } catch (error) {
    if (!isProbablyOfflineError(error)) throw error;
    await queueOfflineAgent("agent_chat", payload, queuedFiles, error);
    recordLogEvent("chat", "Chat saved offline", chatPromptPreview(payload), "Saved locally and will replay after reconnect.");
    render();
    return;
  }
  if (form.get("background_job") === "on") {
    try {
      await enqueueJob("agent_chat", payload);
    } catch (error) {
      if (!isProbablyOfflineError(error)) throw error;
      await queueOfflineAgent("agent_chat", payload, [], error);
    }
    recordLogEvent("chat", "Chat queued", chatPromptPreview(payload), "Background job queued for the worker.");
    render();
    return;
  }
  try {
    state.chatResponse = await apiPost<AgentChatResponse>("/api/agent/chat", payload);
  } catch (error) {
    if (!isProbablyOfflineError(error)) throw error;
    await queueOfflineAgent("agent_chat", payload, [], error);
    recordLogEvent("chat", "Chat saved offline", chatPromptPreview(payload), "Saved locally and will replay after reconnect.");
    render();
    return;
  }
  recordLogEvent("chat", "Chat sent", chatPromptPreview(payload), state.chatResponse.message);
  await refreshChatHistory();
  if (state.chatResponse.proposal) {
    state.proposal = state.chatResponse.proposal;
    state.notice = "Chat drafted a proposal. Review before applying.";
  } else {
    state.notice = "Chat answered from app data.";
  }
  if (state.chatResponse.proposal) {
    await refreshProposals();
    return;
  }
  render();
}

async function onLabelScan(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.household || !state.person) return;
  const form = new FormData(event.currentTarget as HTMLFormElement);
  const quantityG = optionalNumber(form, "quantity_g");
  const queuedFiles = queuedFilesFromForm(form, "attachment", "nutrition_label_image");
  const payload = {
    household_id: state.household.id,
    person_id: state.person.id,
    table_text: optionalText(form, "table_text") ?? "",
    barcode: optionalText(form, "barcode"),
    set_as_default: true,
    attachment_id: null as string | null,
    attachment_ids: [] as string[],
    logged_at_local: quantityG === null ? null : requiredText(form, "logged_at_local"),
    quantity_g: quantityG,
    meal_type: quantityG === null ? null : requiredText(form, "meal_type")
  };
  if (!navigator.onLine) {
    await queueOfflineAgent("agent_label_scan", payload, queuedFiles);
    recordLogEvent("label", "Product label saved offline", labelScanPromptPreview(payload), "Saved locally with upload evidence for replay.");
    render();
    return;
  }
  let attachments: AttachmentObject[] = [];
  try {
    attachments = await uploadOptionalAttachments(form, "attachment", "nutrition_label_image");
    payload.attachment_ids = attachments.map((attachment) => attachment.id);
    payload.attachment_id = payload.attachment_ids[0] ?? null;
  } catch (error) {
    if (!isProbablyOfflineError(error)) throw error;
    await queueOfflineAgent("agent_label_scan", payload, queuedFiles, error);
    return;
  }
  if (form.get("background_job") === "on") {
    try {
      await enqueueJob("agent_label_scan", payload);
    } catch (error) {
      if (!isProbablyOfflineError(error)) throw error;
      await queueOfflineAgent(
        "agent_label_scan",
        attachments.length ? payload : { ...payload, attachment_id: null, attachment_ids: [] },
        attachments.length ? [] : queuedFiles,
        error
      );
      recordLogEvent("label", "Product label saved offline", labelScanPromptPreview(payload), "Saved locally with upload evidence for replay.");
      render();
    }
    return;
  }
  try {
    state.proposal = await apiPost<Proposal>("/api/agent/label-scan", payload);
  } catch (error) {
    if (!isProbablyOfflineError(error)) throw error;
    await queueOfflineAgent(
      "agent_label_scan",
      attachments.length ? payload : { ...payload, attachment_id: null, attachment_ids: [] },
      attachments.length ? [] : queuedFiles,
      error
    );
    recordLogEvent("label", "Product label saved offline", labelScanPromptPreview(payload), "Saved locally with upload evidence for replay.");
    render();
    return;
  }
  recordLogEvent("label", "Product label sent", labelScanPromptPreview(payload), state.proposal.summary);
  state.notice = attachments.length
    ? `Food version proposal drafted with ${attachments.length} attachment${attachments.length === 1 ? "" : "s"}.`
    : "Food version proposal drafted.";
  await refreshProposals();
}

async function onRecipe(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.household || !state.person) return;
  const form = new FormData(event.currentTarget as HTMLFormElement);
  const quantityG = optionalNumber(form, "quantity_g");
  const payload = {
    household_id: state.household.id,
    person_id: state.person.id,
    recipe_text: requiredText(form, "recipe_text"),
    logged_at_local: quantityG === null ? null : requiredText(form, "logged_at_local"),
    quantity_g: quantityG,
    meal_type: quantityG === null ? null : requiredText(form, "meal_type")
  };
  if (form.get("background_job") === "on") {
    try {
      await enqueueJob("agent_recipe", payload);
    } catch (error) {
      if (!isProbablyOfflineError(error)) throw error;
      await queueOfflineAgent("agent_recipe", payload, [], error);
    }
    recordLogEvent("recipe", "Recipe queued", recipePromptPreview(payload), "Background job queued for recipe drafting.");
    render();
    return;
  }
  try {
    state.proposal = await apiPost<Proposal>("/api/agent/recipe", payload);
  } catch (error) {
    if (!isProbablyOfflineError(error)) throw error;
    await queueOfflineAgent("agent_recipe", payload, [], error);
    recordLogEvent("recipe", "Recipe saved offline", recipePromptPreview(payload), "Saved locally and will replay after reconnect.");
    render();
    return;
  }
  recordLogEvent("recipe", "Recipe sent", recipePromptPreview(payload), state.proposal.summary);
  state.notice = "Recipe proposal drafted.";
  await refreshProposals();
}

async function onExportData(): Promise<void> {
  const exported = await apiGet<Record<string, unknown>>("/api/exports/full");
  state.exportText = JSON.stringify(exported, null, 2);
  state.notice = "Export generated.";
  render();
}

async function onImportData(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  const form = new FormData(event.currentTarget as HTMLFormElement);
  const raw = requiredText(form, "import_json");
  const payload = JSON.parse(raw) as {
    data?: { households?: Household[]; people?: Person[] };
  };
  await apiPost("/api/imports/full", payload as Record<string, unknown>);
  const household = payload.data?.households?.[0] ?? null;
  state.household = household;
  state.people = household ? await apiGet<Person[]>(`/api/people?household_id=${household.id}`) : [];
  state.person = state.people[0] ?? null;
  clearPersonScopedState();
  state.exportText = raw;
  saveSession();
  state.notice = "Import completed.";
  await refreshAllReadSurfaces();
}

async function confirmProposal(): Promise<void> {
  if (!state.proposal) return;
  state.proposal = await apiPost<Proposal>(`/api/proposals/${state.proposal.id}/confirm`, {});
  if (
    state.proposal.proposal_type === "food_version_from_label" ||
    state.proposal.proposal_type === "food_version_from_lookup" ||
    state.proposal.proposal_type === "recipe_food_version"
  ) {
    addAppliedFoodProposalToLocalLibrary(state.proposal);
  }
  state.notice = "Proposal applied.";
  await refreshAllReadSurfaces();
}

async function rejectProposal(): Promise<void> {
  if (!state.proposal) return;
  state.proposal = await apiPost<Proposal>(`/api/proposals/${state.proposal.id}/reject`, {});
  state.notice = "Proposal rejected.";
  await refreshProposals();
}

async function enqueueJob(
  jobType: string,
  payload: Record<string, unknown>,
  clientRequestId: string | null = null
): Promise<void> {
  const job = await apiPost<BackgroundJob>("/api/jobs", {
    job_type: jobType,
    payload,
    client_request_id: clientRequestId
  });
  replaceJob(job);
  syncJobPolling();
  state.notice = `${jobLabel(job.job_type)} queued for the worker.`;
  render();
}

async function adoptJobProposal(job: BackgroundJob): Promise<void> {
  const proposalId = typeof job.result.proposal_id === "string" ? job.result.proposal_id : null;
  if (!proposalId || job.status !== "succeeded") return;
  state.proposal = await apiGet<Proposal>(`/api/proposals/${proposalId}`);
}

async function adoptJobChat(job: BackgroundJob): Promise<void> {
  const chatTurnId = typeof job.result.chat_turn_id === "string" ? job.result.chat_turn_id : null;
  if (!chatTurnId || job.status !== "succeeded") return;
  await openChatTurn(chatTurnId, "Loaded job chat answer.");
}

async function openChatTurn(chatTurnId: string, notice: string): Promise<void> {
  await refreshChatHistory();
  const turn = state.chatHistory.find((turn) => turn.id === chatTurnId);
  if (!turn) {
    state.notice = "Chat answer was not found in recent history.";
    return;
  }
  state.chatResponse = {
    run_id: turn.agent_run_id,
    person_id: turn.person_id,
    message: turn.assistant_message,
    behavior_label: turn.behavior_label,
    citations: turn.citations,
    proposal_id: turn.proposal_id,
    proposal: null
  };
  state.notice = notice;
}

function replaceJob(job: BackgroundJob): void {
  const existing = state.jobs.filter((item) => item.id !== job.id);
  state.jobs = [job, ...existing].sort((left, right) => right.created_at.localeCompare(left.created_at));
}

async function refreshSummary(): Promise<void> {
  if (!state.person) {
    render();
    return;
  }
  state.summary = await apiGet<DaySummary>(`/api/diary/day?person_id=${state.person.id}&day=${state.selectedDay}`);
  state.activeGoal = await fetchActiveGoal(state.person.id, state.selectedDay);
  render();
}

async function refreshReview(): Promise<void> {
  if (!state.person) {
    state.reviewNotes = [];
    render();
    return;
  }
  state.weightTrend = await apiGet<WeightTrend>(`/api/weights/trend?person_id=${state.person.id}`);
  state.activeGoal = await fetchActiveGoal(state.person.id, state.selectedDay);
  const weekRange = weekRangeForDay(state.selectedDay);
  state.week = await apiGet<WeekSummary>(
    `/api/summaries/week?person_id=${state.person.id}&start=${weekRange.start}&end=${weekRange.end}`
  );
  state.reviewNotes = await apiGet<ReviewNote[]>(`/api/review-notes?person_id=${state.person.id}`);
  render();
}

async function refreshJobs(): Promise<void> {
  if (!state.person) {
    state.jobs = [];
    syncJobPolling();
    render();
    return;
  }
  state.jobs = await apiGet<BackgroundJob[]>(`/api/jobs?person_id=${state.person.id}`);
  syncJobPolling();
  render();
}

async function refreshProposals(): Promise<void> {
  if (!state.person) {
    state.proposalQueue = [];
    render();
    return;
  }
  state.proposalQueue = await apiGet<Proposal[]>(`/api/proposals?person_id=${state.person.id}`);
  render();
}

async function refreshAllReadSurfaces(): Promise<void> {
  if (!state.person) {
    await refreshFoodLibrary();
    state.reviewNotes = [];
    state.proposalQueue = [];
    state.jobs = [];
    syncJobPolling();
    render();
    return;
  }
  await refreshFoodLibrary();
  state.summary = await apiGet<DaySummary>(`/api/diary/day?person_id=${state.person.id}&day=${state.selectedDay}`);
  state.weightTrend = await apiGet<WeightTrend>(`/api/weights/trend?person_id=${state.person.id}`);
  state.activeGoal = await fetchActiveGoal(state.person.id, state.selectedDay);
  const weekRange = weekRangeForDay(state.selectedDay);
  state.week = await apiGet<WeekSummary>(
    `/api/summaries/week?person_id=${state.person.id}&start=${weekRange.start}&end=${weekRange.end}`
  );
  state.reviewNotes = await apiGet<ReviewNote[]>(`/api/review-notes?person_id=${state.person.id}`);
  state.proposalQueue = await apiGet<Proposal[]>(`/api/proposals?person_id=${state.person.id}`);
  state.jobs = await apiGet<BackgroundJob[]>(`/api/jobs?person_id=${state.person.id}`);
  await refreshChatHistory();
  syncJobPolling();
  render();
}

async function refreshChatHistory(): Promise<void> {
  if (!state.person) {
    state.chatHistory = [];
    return;
  }
  state.chatHistory = await apiGet<AgentChatTurn[]>(
    `/api/agent/chat-history?person_id=${state.person.id}`
  );
}

async function refreshFoodLibrary(): Promise<void> {
  if (!state.household) {
    state.foods = [];
    return;
  }
  const params = new URLSearchParams({ household_id: state.household.id });
  if (state.person) {
    params.set("person_id", state.person.id);
  }
  state.foods = await apiGet<FoodResponse[]>(`/api/foods?${params.toString()}`);
}

async function hydrateStoredSession(): Promise<void> {
  const raw = localStorage.getItem(sessionStorageKey);
  if (!raw) return;
  try {
    const saved = JSON.parse(raw) as {
      household: Household;
      person_id: string | null;
      selected_day?: string | null;
    };
    state.household = saved.household;
    state.selectedDay = saved.selected_day ?? state.selectedDay;
    state.people = await apiGet<Person[]>(`/api/people?household_id=${saved.household.id}`);
    state.person =
      state.people.find((person) => person.id === saved.person_id) ?? state.people[0] ?? null;
    if (state.person) {
      await refreshAllReadSurfaces();
      return;
    }
  } catch (error) {
    if (isProbablyOfflineError(error)) {
      state.notice = "Offline mode: saved notes remain available in the outbox.";
      render();
      return;
    }
    localStorage.removeItem(sessionStorageKey);
  }
  render();
}

function saveSession(): void {
  if (!state.household) return;
  localStorage.setItem(
    sessionStorageKey,
    JSON.stringify({
      household: state.household,
      person_id: state.person?.id ?? null,
      selected_day: state.selectedDay
    })
  );
}

function clearPersonScopedState(): void {
  state.activeGoal = null;
  state.lookupCandidates = [];
  state.summary = null;
  state.week = null;
  state.weightTrend = null;
  state.reviewNotes = [];
  state.proposal = null;
  state.proposalQueue = [];
  state.chatResponse = null;
  state.chatHistory = [];
  state.jobs = [];
  syncJobPolling();
  state.lastDeletedEntry = null;
}

function registerServiceWorker(): void {
  if (!("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/service-worker.js")
      .then((registration) => {
        if (!registration.active) return;
      })
      .catch(() => {
        state.notice ??= "Offline app shell is unavailable in this browser.";
        render();
      });
  });
}

async function fetchActiveGoal(personId: string, day: string): Promise<GoalProfile | null> {
  const goal = await apiGet<Partial<GoalProfile>>(`/api/goals/active?person_id=${personId}&day=${day}`);
  return goal.id ? (goal as GoalProfile) : null;
}

async function createGoalFromFields(
  personId: string,
  fields: {
    starts_on: string;
    calories_kcal: number;
    protein_g: number;
    carbs_g: number;
    fat_g: number;
    fiber_g: number;
    sodium_mg: number;
    notes: string | null;
  }
): Promise<GoalProfile> {
  return apiPost<GoalProfile>("/api/goals", {
    person_id: personId,
    starts_on: fields.starts_on,
    targets: {
      calories_kcal: fields.calories_kcal,
      protein_g: fields.protein_g,
      carbs_g: fields.carbs_g,
      fat_g: fields.fat_g,
      fiber_g: fields.fiber_g,
      sodium_mg: fields.sodium_mg
    },
    notes: fields.notes
  });
}

async function apiGet<T>(path: string): Promise<T> {
  return parseResponse<T>(await fetch(path));
}

async function apiPost<T = unknown>(path: string, body: Record<string, unknown>): Promise<T> {
  return parseResponse<T>(
    await fetch(path, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body)
    })
  );
}

async function apiPatch<T = unknown>(path: string, body: Record<string, unknown>): Promise<T> {
  return parseResponse<T>(
    await fetch(path, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body)
    })
  );
}

async function apiDelete<T = unknown>(path: string): Promise<T> {
  return parseResponse<T>(await fetch(path, { method: "DELETE" }));
}

async function uploadOptionalAttachments(
  form: FormData,
  key: string,
  objectType: string
): Promise<AttachmentObject[]> {
  if (!state.household || !state.person) return [];
  const files = form
    .getAll(key)
    .filter((file): file is File => file instanceof File && file.size > 0);
  const attachments: AttachmentObject[] = [];
  for (const file of files) {
    attachments.push(
      await apiPost<AttachmentObject>("/api/attachments", {
        household_id: state.household.id,
        person_id: state.person.id,
        object_type: objectType,
        mime_type: file.type || "application/octet-stream",
        filename: file.name || null,
        content_base64: await fileToBase64(file),
        retention_policy: "keep"
      })
    );
  }
  return attachments;
}

function queuedFilesFromForm(form: FormData, key: string, objectType: string): OfflineOutboxFile[] {
  return form
    .getAll(key)
    .filter((file): file is File => file instanceof File && file.size > 0)
    .map((file) => ({
      field: key,
      object_type: objectType,
      filename: file.name || null,
      mime_type: file.type || "application/octet-stream",
      blob: file
    }));
}

async function fileToBase64(file: File): Promise<string> {
  return blobToBase64(file);
}

async function blobToBase64(blob: Blob): Promise<string> {
  const buffer = await blob.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

async function parseResponse<T>(response: Response): Promise<T> {
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error?.message ?? `Request failed: ${response.status}`);
  }
  return body as T;
}

function requiredText(form: FormData, key: string): string {
  const value = form.get(key);
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`Missing ${key}`);
  }
  return value.trim();
}

function optionalText(form: FormData, key: string): string | null {
  const value = form.get(key);
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function numberField(form: FormData, key: string): number {
  return Number(requiredText(form, key));
}

function optionalNumber(form: FormData, key: string): number | null {
  const value = optionalText(form, key);
  return value === null ? null : Number(value);
}

function metric(label: string, value: string, unit: string): string {
  return `
    <div class="metric">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <em>${escapeHtml(unit)}</em>
    </div>
  `;
}

function foodLabel(item: FoodResponse): string {
  const brand = item.food.brand ? `${item.food.brand} ` : "";
  return `${brand}${item.food.name} · ${item.version.label}`;
}

function filteredFoods(): FoodResponse[] {
  return state.foods.filter(matchesFoodFilter);
}

function matchesFoodFilter(item: FoodResponse): boolean {
  const query = normalizeSearch(state.foodFilter);
  if (!query) return true;
  return [
    item.food.name,
    item.food.brand,
    item.version.label,
    foodLabel(item),
    ...item.aliases,
    ...item.barcodes,
    ...item.attachments.map((attachment) => attachment.filename ?? attachment.object_type),
    foodContextText(item),
    item.food.default_version_id,
    item.version.id
  ]
    .filter((value): value is string => typeof value === "string")
    .some((value) => normalizeSearch(value).includes(query));
}

function normalizeSearch(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function evidenceBadge(entry: SummaryEntry): string {
  const status = entry.evidence_status || "unknown";
  const className = normalizeSearch(status).replace(/[^a-z0-9-]/g, "-") || "unknown";
  const confidence = Math.round(entry.confidence * 100);
  return `<span class="evidence-badge evidence-${className}">${escapeHtml(evidenceLabel(status))} · ${confidence}% confidence</span>`;
}

function evidenceLabel(status: string): string {
  const labels: Record<string, string> = {
    estimated: "Estimated",
    exact: "Exact",
    inferred: "Inferred",
    looked_up: "Looked up",
    unknown: "Unknown"
  };
  return labels[status] ?? titleCase(status.replace(/_/g, " "));
}

function mealOptions(selected: string): string {
  return ["breakfast", "lunch", "snack", "dinner", "late"]
    .map((meal) => `<option value="${meal}" ${meal === selected ? "selected" : ""}>${titleCase(meal)}</option>`)
    .join("");
}

function proposalFoodOptions(entry: ProposalEntry): string {
  const currentLabel = `${entry.food_name} · ${entry.food_version_label}`;
  const current = `<option value="${entry.food_version_id}" selected>${escapeHtml(currentLabel)}</option>`;
  const saved = state.foods
    .filter((item) => item.version.id !== entry.food_version_id)
    .map((item) => `<option value="${item.version.id}">${escapeHtml(foodOptionLabel(item))}</option>`)
    .join("");
  return `${current}${saved}`;
}

function addAppliedFoodProposalToLocalLibrary(proposal: Proposal): void {
  const [foodId, versionId] = proposal.applied_record_ids ?? [];
  const nutrients = proposal.payload.nutrients_per_100g as Nutrients | undefined;
  if (!foodId || !versionId || !nutrients) return;
  const food: Food = {
    id: String(foodId),
    name: String(proposal.payload.food_name ?? ""),
    brand: proposal.payload.brand ? String(proposal.payload.brand) : null,
    default_version_id: String(versionId)
  };
  const version: FoodVersion = {
    id: String(versionId),
    food_id: String(foodId),
    label: String(proposal.payload.version_label ?? "label scan"),
    nutrients_per_100g: nutrients,
    serving_size_g:
      typeof proposal.payload.serving_size_g === "number" ? proposal.payload.serving_size_g : null
  };
  const barcode = typeof proposal.payload.barcode === "string" ? proposal.payload.barcode : null;
  const aliases = typeof proposal.payload.food_name === "string" ? [proposal.payload.food_name] : [];
  state.foods = [
    ...state.foods,
    {
      food,
      version,
      aliases,
      barcodes: barcode ? [barcode] : [],
      is_default: true,
      last_used_at: null,
      attachments: []
    }
  ];
}

function zeroNutrients(): Nutrients {
  return {
    calories_kcal: 0,
    protein_g: 0,
    carbs_g: 0,
    fat_g: 0,
    fiber_g: 0,
    sodium_mg: 0
  };
}

function defaultDateTime(time: string): string {
  return `${state.selectedDay}T${time}`;
}

function weekRangeForDay(day: string): { start: string; end: string } {
  const start = dateFromInputValue(day);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  return {
    start: localDateInputValue(start),
    end: localDateInputValue(end)
  };
}

function dateFromInputValue(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function localDateInputValue(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDateTime(value: string): string {
  return value.slice(0, 19).replace("T", " ");
}

function titleCase(value: string): string {
  return value.slice(0, 1).toUpperCase() + value.slice(1);
}

function jobLabel(jobType: string): string {
  const labels: Record<string, string> = {
    agent_text_meal: "Meal note",
    agent_label_scan: "Product label",
    agent_recipe: "Recipe",
    agent_chat: "Agent chat"
  };
  return labels[jobType] ?? jobType;
}

function foodEvidenceLabel(attachments: AttachmentObject[]): string {
  if (!attachments.length) return "";
  const filenames = attachments
    .map((attachment) => attachment.filename ?? attachment.object_type)
    .slice(0, 2)
    .join(", ");
  const suffix = attachments.length > 2 ? ` +${attachments.length - 2}` : "";
  return `<span class="food-evidence">label evidence · ${escapeHtml(filenames)}${suffix}</span>`;
}

function foodOptionLabel(item: FoodResponse): string {
  const context = foodContextText(item);
  return context ? `${foodLabel(item)} · ${context}` : foodLabel(item);
}

function foodContextLabel(item: FoodResponse): string {
  const context = foodContextText(item);
  return context ? `<span class="food-context">${escapeHtml(context)}</span>` : "";
}

function foodContextText(item: FoodResponse): string {
  const parts = [];
  if (item.is_default) {
    parts.push("current default");
  }
  if (item.last_used_at) {
    parts.push(`last used ${item.last_used_at.slice(0, 10)}`);
  }
  return parts.join(" · ");
}

function syncJobPolling(): void {
  if (hasActiveJobs()) {
    if (jobPollTimer !== null) return;
    jobPollTimer = window.setInterval(() => {
      void refreshJobs();
    }, 4000);
    return;
  }
  if (jobPollTimer === null) return;
  window.clearInterval(jobPollTimer);
  jobPollTimer = null;
}

function hasActiveJobs(): boolean {
  return state.jobs.some((job) => isActiveJobStatus(job.status));
}

function isActiveJobStatus(status: string): boolean {
  return status === "pending" || status === "running";
}

function signed(value: number): string {
  return value > 0 ? `+${value}` : `${value}`;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => {
    const replacements: Record<string, string> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;"
    };
    return replacements[char];
  });
}
