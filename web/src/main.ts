import "./styles.css";

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
};
type Food = { id: string; name: string; brand: string | null; default_version_id: string; archived?: boolean };
type FoodResponse = { food: Food; version: FoodVersion };
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
  agent_run: {
    id: string;
    settings: Record<string, string | number | boolean>;
    status: string;
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
type BackgroundJob = {
  id: string;
  job_type: string;
  status: string;
  payload: Record<string, unknown>;
  result: Record<string, unknown>;
  last_error: string | null;
  attempts: number;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
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
  chatResponse: AgentChatResponse | null;
  jobs: BackgroundJob[];
  lastDeletedEntry: DiaryEntryRecord | null;
  exportText: string;
  notice: string | null;
  errorMessage: string | null;
};

const sessionStorageKey = "health-monitor.session.v1";
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
  chatResponse: null,
  jobs: [],
  lastDeletedEntry: null,
  exportText: "",
  notice: null,
  errorMessage: null
};

const appRoot = requireAppRoot();

render();
void hydrateStoredSession();
registerServiceWorker();

function render(): void {
  appRoot.innerHTML = `
    <section class="shell">
      <header class="topbar">
        <div>
          <p class="eyebrow">Private household tracker</p>
          <h1>Health Monitor</h1>
        </div>
        ${renderProfileSwitcher("topbar")}
      </header>

      ${renderNoticeBanner()}

      <section class="workspace">
        <div class="primary">
          ${renderToday()}
          ${renderReview()}
          ${renderProposal()}
          ${renderJobs()}
        </div>
        <aside class="side">
          ${renderSetup()}
          ${renderGoalForm()}
          ${renderFoodForm()}
          ${renderFoodLookup()}
          ${renderManualLog()}
          ${renderWeightForm()}
          ${renderTextMeal()}
          ${renderAgentChat()}
          ${renderLabelScan()}
          ${renderRecipeForm()}
          ${renderDataPortability()}
        </aside>
      </section>
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
    return `<div class="person-switch">No profile</div>`;
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

function renderNoticeBanner(): string {
  if (state.errorMessage) {
    return `<div class="notice notice-error" role="alert">${escapeHtml(state.errorMessage)}</div>`;
  }
  if (!state.notice) {
    return "";
  }
  return `<div class="notice">${escapeHtml(state.notice)}${
    state.lastDeletedEntry ? ` <button id="undo-delete" type="button">Undo</button>` : ""
  }</div>`;
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
                <span>${escapeHtml(entry.food_version_label)} · ${escapeHtml(entry.source)}</span>
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
    <section class="today">
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
    <section class="today">
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
      <section class="proposal-empty">
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
                  <input name="quantity_g" type="number" step="0.1" value="${entry.quantity_g}" aria-label="Proposal quantity grams" />
                  <select name="meal_type" aria-label="Proposal meal type">${mealOptions(entry.meal_type)}</select>
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
  return `
    <section class="proposal">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Agent proposal</p>
          <h2>${escapeHtml(state.proposal.status)}</h2>
          <p>${escapeHtml(state.proposal.summary)}</p>
        </div>
        <div class="button-row">
          <button id="reject-proposal" type="button">Reject</button>
          ${canConfirm ? `<button id="confirm-proposal" class="primary-action" type="button">Confirm</button>` : ""}
        </div>
      </div>
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
      return `
        <li>
          <div>
            <strong>${escapeHtml(jobLabel(job.job_type))}</strong>
            <span>${escapeHtml(job.status)} · ${job.attempts} attempt${job.attempts === 1 ? "" : "s"} · ${escapeHtml(job.created_at.slice(0, 19))}</span>
            ${
              job.last_error
                ? `<span class="job-error">${escapeHtml(job.last_error)}</span>`
                : proposalId
                  ? `<span>Proposal ${escapeHtml(proposalId)}</span>`
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
          <span>${item.version.nutrients_per_100g.calories_kcal} kcal · ${item.version.nutrients_per_100g.protein_g} g protein / 100g</span>
          <span>${item.version.nutrients_per_100g.fiber_g} g fiber · ${item.version.nutrients_per_100g.sodium_mg} mg sodium / 100g</span>
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
      <label>Find saved food <input class="food-filter" data-filter-id="library" type="search" value="${escapeHtml(state.foodFilter)}" placeholder="name, brand, label" ${state.foods.length ? "" : "disabled"} /></label>
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
    .map((item) => `<option value="${item.version.id}">${escapeHtml(foodLabel(item))}</option>`)
    .join("");
  return `
    <form id="manual-log-form" class="panel">
      <p class="eyebrow">Manual log</p>
      <h2>Diary entry</h2>
      <label>Find food <input class="food-filter" data-filter-id="manual" type="search" value="${escapeHtml(state.foodFilter)}" placeholder="queijo, iogurte, protein" ${state.person && state.foods.length ? "" : "disabled"} /></label>
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

function renderTextMeal(): string {
  const disabled = state.person ? "" : "disabled";
  return `
    <form id="text-meal-form" class="panel">
      <p class="eyebrow">Agent input</p>
      <h2>Text meal</h2>
      <label>Text <input name="text" value="10am, 100g queijo" ${disabled} /></label>
      <label>Model profile <input name="model_profile" value="ollama-local" ${disabled} /></label>
      <label>Effort
        <select name="effort" ${disabled}>
          <option value="low">Low</option>
          <option value="medium" selected>Medium</option>
          <option value="high">High</option>
        </select>
      </label>
      <label>Max loops <input name="max_tool_loops" type="number" value="4" min="1" max="12" ${disabled} /></label>
      <label class="check-row"><input name="external_lookup" type="checkbox" checked ${disabled} /> External lookup</label>
      <label class="check-row"><input name="background_job" type="checkbox" ${disabled} /> Run in background</label>
      <button type="submit" ${disabled}>Draft proposal</button>
    </form>
  `;
}

function renderAgentChat(): string {
  const disabled = state.person ? "" : "disabled";
  const response = state.chatResponse;
  return `
    <form id="agent-chat-form" class="panel">
      <p class="eyebrow">Agent chat</p>
      <h2>Ask / correct</h2>
      <textarea name="message" ${disabled}>Why was ${state.selectedDay} high in calories?</textarea>
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
      <label class="check-row"><input name="background_job" type="checkbox" ${disabled} /> Run in background</label>
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
    </form>
  `;
}

function renderLabelScan(): string {
  const disabled = state.household && state.person ? "" : "disabled";
  return `
    <form id="label-scan-form" class="panel">
      <p class="eyebrow">Label scan</p>
      <h2>Nutrition table</h2>
      <label>Image <input name="attachment" type="file" accept="image/*" ${disabled} /></label>
      <label>Barcode <input name="barcode" inputmode="numeric" placeholder="optional separate scan" ${disabled} /></label>
      <div class="grid-two">
        <label>Log time <input name="logged_at_local" type="datetime-local" value="${defaultDateTime("10:00")}" ${disabled} /></label>
        <label>Log grams <input name="quantity_g" type="number" step="0.1" placeholder="optional" ${disabled} /></label>
        <label>Meal
          <select name="meal_type" ${disabled}>
            ${mealOptions("breakfast")}
          </select>
        </label>
      </div>
      <textarea name="table_text" placeholder="Optional when an image is attached" ${disabled}>Produto: Iogurte Batavo Protein
Marca: Batavo
Porcao: 170 g
Valor energetico: 120 kcal
Proteinas: 15 g
Carboidratos: 10 g
Gorduras totais: 2 g
Codigo de barras: 7891000000000</textarea>
      <label class="check-row"><input name="background_job" type="checkbox" ${disabled} /> Run in background</label>
      <button type="submit" ${disabled}>Draft food version</button>
    </form>
  `;
}

function renderRecipeForm(): string {
  const disabled = state.household && state.person ? "" : "disabled";
  return `
    <form id="recipe-form" class="panel">
      <p class="eyebrow">Batch food</p>
      <h2>Recipe</h2>
      <div class="grid-two">
        <label>Log time <input name="logged_at_local" type="datetime-local" value="${defaultDateTime("12:30")}" ${disabled} /></label>
        <label>Log grams <input name="quantity_g" type="number" step="0.1" placeholder="optional" ${disabled} /></label>
        <label>Meal
          <select name="meal_type" ${disabled}>
            ${mealOptions("lunch")}
          </select>
        </label>
      </div>
      <textarea name="recipe_text" ${disabled}>Recipe: Batch breakfast mix
Yield: 1000 g
Ingredients:
500g queijo
500g banana</textarea>
      <label class="check-row"><input name="background_job" type="checkbox" ${disabled} /> Run in background</label>
      <button type="submit" ${disabled}>Draft recipe</button>
    </form>
  `;
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
  document.querySelector<HTMLFormElement>("#import-form")?.addEventListener("submit", safeAsync(onImportData));
  document
    .querySelectorAll<HTMLSelectElement>(".profile-select")
    .forEach((select) => select.addEventListener("change", safeAsync(onProfileSelect)));
  document
    .querySelectorAll<HTMLInputElement>(".food-filter")
    .forEach((input) => input.addEventListener("input", onFoodFilterInput));
  document.querySelector<HTMLInputElement>("#selected-day")?.addEventListener("change", safeAsync(onSelectedDayChange));
  document.querySelector<HTMLButtonElement>("#refresh-summary")?.addEventListener("click", safeAsync(refreshSummary));
  document.querySelector<HTMLButtonElement>("#refresh-review")?.addEventListener("click", safeAsync(refreshReview));
  document.querySelector<HTMLButtonElement>("#refresh-jobs")?.addEventListener("click", safeAsync(refreshJobs));
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
    quantity_g: numberField(form, "quantity_g"),
    meal_type: requiredText(form, "meal_type")
  });
  state.notice = "Proposal entry updated.";
  render();
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
  render();
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
  render();
}

async function onJobProcess(event: Event): Promise<void> {
  const jobId = (event.currentTarget as HTMLButtonElement).dataset.jobId;
  if (!jobId) return;
  const job = await apiPost<BackgroundJob>(`/api/jobs/${jobId}/process`, {});
  replaceJob(job);
  await adoptJobProposal(job);
  state.notice = `Job ${job.status}.`;
  render();
}

async function onJobLoadProposal(event: Event): Promise<void> {
  const proposalId = (event.currentTarget as HTMLButtonElement).dataset.proposalId;
  if (!proposalId) return;
  state.proposal = await apiGet<Proposal>(`/api/proposals/${proposalId}`);
  state.notice = "Loaded job proposal. Review before applying.";
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
  state.foods = [...state.foods, { food: created.food, version: created.version }];
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
      external_lookup: form.get("external_lookup") === "on"
    }
  };
  if (form.get("background_job") === "on") {
    await enqueueJob("agent_text_meal", payload);
    return;
  }
  state.proposal = await apiPost<Proposal>("/api/agent/text-meal", payload);
  state.notice = "Proposal drafted. Review before applying.";
  render();
}

async function onAgentChat(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.person) return;
  const form = new FormData(event.currentTarget as HTMLFormElement);
  const payload = {
    person_id: state.person.id,
    message: requiredText(form, "message"),
    today: state.selectedDay,
    agent_settings: {
      model_profile: requiredText(form, "model_profile"),
      effort: requiredText(form, "effort"),
      max_tool_loops: numberField(form, "max_tool_loops")
    }
  };
  if (form.get("background_job") === "on") {
    await enqueueJob("agent_chat", payload);
    return;
  }
  state.chatResponse = await apiPost<AgentChatResponse>("/api/agent/chat", payload);
  if (state.chatResponse.proposal) {
    state.proposal = state.chatResponse.proposal;
    state.notice = "Chat drafted a proposal. Review before applying.";
  } else {
    state.notice = "Chat answered from app data.";
  }
  render();
}

async function onLabelScan(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.household || !state.person) return;
  const form = new FormData(event.currentTarget as HTMLFormElement);
  const attachment = await uploadOptionalAttachment(form, "attachment", "nutrition_label_image");
  const quantityG = optionalNumber(form, "quantity_g");
  const payload = {
    household_id: state.household.id,
    person_id: state.person.id,
    table_text: optionalText(form, "table_text") ?? "",
    barcode: optionalText(form, "barcode"),
    set_as_default: true,
    attachment_id: attachment?.id ?? null,
    logged_at_local: quantityG === null ? null : requiredText(form, "logged_at_local"),
    quantity_g: quantityG,
    meal_type: quantityG === null ? null : requiredText(form, "meal_type")
  };
  if (form.get("background_job") === "on") {
    await enqueueJob("agent_label_scan", payload);
    return;
  }
  state.proposal = await apiPost<Proposal>("/api/agent/label-scan", payload);
  state.notice = attachment
    ? "Food version proposal drafted with attachment evidence."
    : "Food version proposal drafted.";
  render();
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
    await enqueueJob("agent_recipe", payload);
    return;
  }
  state.proposal = await apiPost<Proposal>("/api/agent/recipe", payload);
  state.notice = "Recipe proposal drafted.";
  render();
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
  render();
}

async function enqueueJob(jobType: string, payload: Record<string, unknown>): Promise<void> {
  const job = await apiPost<BackgroundJob>("/api/jobs", {
    job_type: jobType,
    payload
  });
  replaceJob(job);
  state.notice = `${jobLabel(job.job_type)} queued for the worker.`;
  render();
}

async function adoptJobProposal(job: BackgroundJob): Promise<void> {
  const proposalId = typeof job.result.proposal_id === "string" ? job.result.proposal_id : null;
  if (!proposalId || job.status !== "succeeded") return;
  state.proposal = await apiGet<Proposal>(`/api/proposals/${proposalId}`);
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
    render();
    return;
  }
  state.jobs = await apiGet<BackgroundJob[]>(`/api/jobs?person_id=${state.person.id}`);
  render();
}

async function refreshAllReadSurfaces(): Promise<void> {
  if (!state.person) {
    await refreshFoodLibrary();
    state.reviewNotes = [];
    state.jobs = [];
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
  state.jobs = await apiGet<BackgroundJob[]>(`/api/jobs?person_id=${state.person.id}`);
  render();
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
  } catch {
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
  state.chatResponse = null;
  state.jobs = [];
  state.lastDeletedEntry = null;
}

function registerServiceWorker(): void {
  if (!("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/service-worker.js")
      .then((registration) => {
        if (!registration.active) return;
        state.notice ??= "App shell is available offline.";
        render();
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

async function uploadOptionalAttachment(
  form: FormData,
  key: string,
  objectType: string
): Promise<AttachmentObject | null> {
  if (!state.household || !state.person) return null;
  const file = form.get(key);
  if (!(file instanceof File) || file.size === 0) return null;
  return apiPost<AttachmentObject>("/api/attachments", {
    household_id: state.household.id,
    person_id: state.person.id,
    object_type: objectType,
    mime_type: file.type || "application/octet-stream",
    filename: file.name || null,
    content_base64: await fileToBase64(file),
    retention_policy: "keep"
  });
}

async function fileToBase64(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
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

function mealOptions(selected: string): string {
  return ["breakfast", "lunch", "snack", "dinner", "late"]
    .map((meal) => `<option value="${meal}" ${meal === selected ? "selected" : ""}>${titleCase(meal)}</option>`)
    .join("");
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
  state.foods = [...state.foods, { food, version }];
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

function titleCase(value: string): string {
  return value.slice(0, 1).toUpperCase() + value.slice(1);
}

function jobLabel(jobType: string): string {
  const labels: Record<string, string> = {
    agent_text_meal: "Text meal",
    agent_label_scan: "Label scan",
    agent_recipe: "Recipe",
    agent_chat: "Agent chat"
  };
  return labels[jobType] ?? jobType;
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
