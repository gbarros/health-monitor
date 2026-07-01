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
type Food = { id: string; name: string; brand: string | null; default_version_id: string };
type FoodResponse = { food: Food; version: FoodVersion };
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

type AppState = {
  household: Household | null;
  people: Person[];
  person: Person | null;
  activeGoal: GoalProfile | null;
  foods: FoodResponse[];
  lookupCandidates: FoodLookupCandidate[];
  summary: DaySummary | null;
  week: WeekSummary | null;
  weightTrend: WeightTrend | null;
  proposal: Proposal | null;
  chatResponse: AgentChatResponse | null;
  lastDeletedEntry: DiaryEntryRecord | null;
  exportText: string;
  notice: string | null;
};

const today = "2026-07-01";
const sessionStorageKey = "health-monitor.session.v1";
const state: AppState = {
  household: null,
  people: [],
  person: null,
  activeGoal: null,
  foods: [],
  lookupCandidates: [],
  summary: null,
  week: null,
  weightTrend: null,
  proposal: null,
  chatResponse: null,
  lastDeletedEntry: null,
  exportText: "",
  notice: null
};

const appRoot = requireAppRoot();

render();
void hydrateStoredSession();

function render(): void {
  appRoot.innerHTML = `
    <section class="shell">
      <header class="topbar">
        <div>
          <p class="eyebrow">Private household tracker</p>
          <h1>Health Monitor</h1>
        </div>
        <div class="person-switch">${state.person ? escapeHtml(state.person.name) : "No profile"}</div>
      </header>

      ${
        state.notice
          ? `<div class="notice">${escapeHtml(state.notice)}${
              state.lastDeletedEntry
                ? ` <button id="undo-delete" type="button">Undo</button>`
                : ""
            }</div>`
          : ""
      }

      <section class="workspace">
        <div class="primary">
          ${renderToday()}
          ${renderReview()}
          ${renderProposal()}
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
          <h2>${summary?.day ?? today}</h2>
        </div>
        <button id="refresh-summary" type="button">Refresh</button>
      </div>
      <div class="metrics">
        ${metric("Calories", `${totals.calories_kcal}`, "kcal")}
        ${metric("Protein", `${totals.protein_g}`, "g")}
        ${metric("Carbs", `${totals.carbs_g}`, "g")}
        ${metric("Fat", `${totals.fat_g}`, "g")}
      </div>
      ${
        target && delta
          ? `<div class="target-strip">
              <span>Target ${target.calories_kcal} kcal</span>
              <span>${signed(delta.calories_kcal)} kcal</span>
              <span>${signed(delta.protein_g)} g protein</span>
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
              <td>${escapeHtml(entry.measured_at.slice(0, 10))}</td>
              <td>${entry.weight_kg} kg</td>
              <td>${escapeHtml(entry.note ?? "")}</td>
            </tr>
          `
        )
        .join("")
    : "";
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
      </div>
      ${
        dailyRows
          ? `<table><thead><tr><th>Day</th><th>Calories</th><th>Protein</th><th>Target</th><th>Carbs</th><th>Fat</th></tr></thead><tbody>${dailyRows}</tbody></table>`
          : `<p class="empty">No weekly review loaded yet.</p>`
      }
      ${
        weightRows
          ? `<section class="meal-band"><h3>Weights</h3><table><thead><tr><th>Date</th><th>Weight</th><th>Note</th></tr></thead><tbody>${weightRows}</tbody></table></section>`
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
      (entry) => `
        <li>
          <strong>${escapeHtml(entry.food_name)}</strong>
          <span>${entry.quantity_g} g · ${entry.nutrients.calories_kcal} kcal · ${entry.nutrients.protein_g} g protein</span>
        </li>
      `
    )
    .join("");
  const payloadDetails =
    state.proposal.proposal_type === "food_version_from_label" ||
    state.proposal.proposal_type === "food_version_from_lookup"
      ? renderFoodVersionProposalPayload(state.proposal)
      : state.proposal.proposal_type === "recipe_food_version"
        ? renderRecipeProposalPayload(state.proposal)
      : state.proposal.proposal_type === "diary_entry_update"
        ? renderDiaryUpdateProposalPayload(state.proposal)
      : state.proposal.proposal_type === "diary_entries_with_estimates"
        ? renderEstimateProposalPayload(state.proposal)
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
          <button id="confirm-proposal" class="primary-action" type="button">Confirm</button>
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

function renderRecipeProposalPayload(proposal: Proposal): string {
  const nutrients = proposal.payload.nutrients_per_100g as Partial<Nutrients> | undefined;
  const ingredients = proposal.payload.ingredients as Array<Record<string, unknown>> | undefined;
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
      <div><dt>Yield</dt><dd>${escapeHtml(String(proposal.payload.yield_g ?? ""))} g</dd></div>
      <div><dt>Calories / 100g</dt><dd>${nutrients?.calories_kcal ?? 0}</dd></div>
      <div><dt>Protein / 100g</dt><dd>${nutrients?.protein_g ?? 0} g</dd></div>
    </dl>
    ${ingredientRows ? `<ul class="evidence-list">${ingredientRows}</ul>` : ""}
  `;
}

function renderSetup(): string {
  if (state.household && state.person) {
    const options = state.people
      .map(
        (person) =>
          `<option value="${person.id}" ${person.id === state.person?.id ? "selected" : ""}>${escapeHtml(person.name)}</option>`
      )
      .join("");
    return `
      <section class="panel">
        <p class="eyebrow">Profile</p>
        <h2>${escapeHtml(state.household.name)}</h2>
        <label>Active person <select id="profile-select">${options}</select></label>
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
      <label>Starts on <input name="starts_on" type="date" value="${today}" ${disabled} /></label>
      <div class="grid-two">
        <label>Calories <input name="calories_kcal" type="number" value="${state.activeGoal?.targets.calories_kcal ?? 2000}" ${disabled} /></label>
        <label>Protein <input name="protein_g" type="number" value="${state.activeGoal?.targets.protein_g ?? 150}" ${disabled} /></label>
        <label>Carbs <input name="carbs_g" type="number" value="${state.activeGoal?.targets.carbs_g ?? 180}" ${disabled} /></label>
        <label>Fat <input name="fat_g" type="number" value="${state.activeGoal?.targets.fat_g ?? 70}" ${disabled} /></label>
      </div>
      <label>Notes <input name="notes" value="${escapeHtml(state.activeGoal?.notes ?? "")}" ${disabled} /></label>
      <button type="submit" ${disabled}>Save targets</button>
    </form>
  `;
}

function renderFoodForm(): string {
  const disabled = state.household ? "" : "disabled";
  const options = state.foods
    .map((item) => `<option value="${item.version.id}">${escapeHtml(foodLabel(item))}</option>`)
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
      </div>
      <label>Serving size g <input name="serving_size_g" type="number" step="0.1" placeholder="optional" ${disabled} /></label>
      <label>Aliases <input name="aliases" value="queijo, queijo minas" ${disabled} /></label>
      <label>Barcode <input name="barcode" placeholder="optional" ${disabled} /></label>
      <button type="submit" ${disabled}>Save food</button>
      ${options ? `<p class="hint">${state.foods.length} food version saved locally.</p>` : ""}
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
  const disabled = state.person && state.foods.length ? "" : "disabled";
  const options = state.foods
    .map((item) => `<option value="${item.version.id}">${escapeHtml(foodLabel(item))}</option>`)
    .join("");
  return `
    <form id="manual-log-form" class="panel">
      <p class="eyebrow">Manual log</p>
      <h2>Diary entry</h2>
      <label>Food <select name="food_version_id" ${disabled}>${options}</select></label>
      <label>Time <input name="logged_at_local" type="datetime-local" value="${today}T10:00" ${disabled} /></label>
      <label>Quantity <input name="quantity_g" type="number" step="0.1" value="100" ${disabled} /></label>
      <button type="submit" ${disabled}>Add entry</button>
    </form>
  `;
}

function renderWeightForm(): string {
  const disabled = state.person ? "" : "disabled";
  return `
    <form id="weight-form" class="panel">
      <p class="eyebrow">Weight</p>
      <h2>Reading</h2>
      <label>Time <input name="measured_at_local" type="datetime-local" value="${today}T08:00" ${disabled} /></label>
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
      <label>Max loops <input name="max_tool_loops" type="number" value="4" min="1" max="12" ${disabled} /></label>
      <label class="check-row"><input name="external_lookup" type="checkbox" checked ${disabled} /> External lookup</label>
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
      <textarea name="message" ${disabled}>Why was 2026-07-01 high in calories?</textarea>
      <div class="grid-two">
        <label>Model profile <input name="model_profile" value="deterministic-local" ${disabled} /></label>
        <label>Max loops <input name="max_tool_loops" type="number" value="4" min="1" max="12" ${disabled} /></label>
      </div>
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
      <textarea name="table_text" ${disabled}>Produto: Iogurte Batavo Protein
Marca: Batavo
Porcao: 170 g
Valor energetico: 120 kcal
Proteinas: 15 g
Carboidratos: 10 g
Gorduras totais: 2 g
Codigo de barras: 7891000000000</textarea>
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
      <textarea name="recipe_text" ${disabled}>Recipe: Batch breakfast mix
Yield: 1000 g
Ingredients:
500g queijo
500g banana</textarea>
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
  document.querySelector<HTMLFormElement>("#setup-form")?.addEventListener("submit", onSetup);
  document.querySelector<HTMLFormElement>("#add-person-form")?.addEventListener("submit", onAddPerson);
  document.querySelector<HTMLFormElement>("#goal-form")?.addEventListener("submit", onGoal);
  document.querySelector<HTMLFormElement>("#food-form")?.addEventListener("submit", onFood);
  document.querySelector<HTMLFormElement>("#food-lookup-form")?.addEventListener("submit", onFoodLookup);
  document.querySelector<HTMLFormElement>("#manual-log-form")?.addEventListener("submit", onManualLog);
  document.querySelector<HTMLFormElement>("#weight-form")?.addEventListener("submit", onWeight);
  document.querySelector<HTMLFormElement>("#text-meal-form")?.addEventListener("submit", onTextMeal);
  document.querySelector<HTMLFormElement>("#agent-chat-form")?.addEventListener("submit", onAgentChat);
  document.querySelector<HTMLFormElement>("#label-scan-form")?.addEventListener("submit", onLabelScan);
  document.querySelector<HTMLFormElement>("#recipe-form")?.addEventListener("submit", onRecipe);
  document.querySelector<HTMLFormElement>("#import-form")?.addEventListener("submit", onImportData);
  document.querySelector<HTMLSelectElement>("#profile-select")?.addEventListener("change", onProfileSelect);
  document.querySelector<HTMLButtonElement>("#refresh-summary")?.addEventListener("click", refreshSummary);
  document.querySelector<HTMLButtonElement>("#refresh-review")?.addEventListener("click", refreshReview);
  document.querySelector<HTMLButtonElement>("#export-data")?.addEventListener("click", onExportData);
  document.querySelector<HTMLButtonElement>("#confirm-proposal")?.addEventListener("click", confirmProposal);
  document.querySelector<HTMLButtonElement>("#reject-proposal")?.addEventListener("click", rejectProposal);
  document.querySelector<HTMLButtonElement>("#undo-delete")?.addEventListener("click", undoLastDelete);
  document
    .querySelectorAll<HTMLFormElement>(".entry-edit-form")
    .forEach((form) => form.addEventListener("submit", onEntryEdit));
  document
    .querySelectorAll<HTMLButtonElement>(".entry-delete")
    .forEach((button) => button.addEventListener("click", onEntryDelete));
  document
    .querySelectorAll<HTMLButtonElement>(".lookup-propose")
    .forEach((button) => button.addEventListener("click", onLookupPropose));
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
    starts_on: today,
    calories_kcal: numberField(form, "target_calories_kcal"),
    protein_g: numberField(form, "target_protein_g"),
    carbs_g: numberField(form, "target_carbs_g"),
    fat_g: numberField(form, "target_fat_g"),
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
  state.activeGoal = null;
  saveSession();
  state.notice = `${person.name} added.`;
  await refreshAllReadSurfaces();
}

async function onProfileSelect(event: Event): Promise<void> {
  const selectedId = (event.currentTarget as HTMLSelectElement).value;
  const selected = state.people.find((person) => person.id === selectedId);
  if (!selected) return;
  state.person = selected;
  state.proposal = null;
  saveSession();
  state.notice = `Switched to ${selected.name}.`;
  await refreshAllReadSurfaces();
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
      fat_g: numberField(form, "fat_g")
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

async function onManualLog(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.person) return;
  const form = new FormData(event.currentTarget as HTMLFormElement);
  await apiPost("/api/diary", {
    person_id: state.person.id,
    logged_at_local: requiredText(form, "logged_at_local"),
    food_version_id: requiredText(form, "food_version_id"),
    quantity_g: numberField(form, "quantity_g"),
    source: "manual"
  });
  state.notice = "Diary entry added.";
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

async function onTextMeal(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.person) return;
  const form = new FormData(event.currentTarget as HTMLFormElement);
  state.proposal = await apiPost<Proposal>("/api/agent/text-meal", {
    person_id: state.person.id,
    logged_at_local: `${today}T10:00:00`,
    text: requiredText(form, "text"),
    agent_settings: {
      model_profile: requiredText(form, "model_profile"),
      max_tool_loops: numberField(form, "max_tool_loops"),
      external_lookup: form.get("external_lookup") === "on"
    }
  });
  state.notice = "Proposal drafted. Review before applying.";
  render();
}

async function onAgentChat(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.person) return;
  const form = new FormData(event.currentTarget as HTMLFormElement);
  state.chatResponse = await apiPost<AgentChatResponse>("/api/agent/chat", {
    person_id: state.person.id,
    message: requiredText(form, "message"),
    today,
    agent_settings: {
      model_profile: requiredText(form, "model_profile"),
      max_tool_loops: numberField(form, "max_tool_loops")
    }
  });
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
  state.proposal = await apiPost<Proposal>("/api/agent/label-scan", {
    household_id: state.household.id,
    person_id: state.person.id,
    table_text: requiredText(form, "table_text"),
    set_as_default: true
  });
  state.notice = "Food version proposal drafted.";
  render();
}

async function onRecipe(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (!state.household || !state.person) return;
  const form = new FormData(event.currentTarget as HTMLFormElement);
  state.proposal = await apiPost<Proposal>("/api/agent/recipe", {
    household_id: state.household.id,
    person_id: state.person.id,
    recipe_text: requiredText(form, "recipe_text")
  });
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

async function refreshSummary(): Promise<void> {
  if (!state.person) {
    render();
    return;
  }
  state.summary = await apiGet<DaySummary>(`/api/diary/day?person_id=${state.person.id}&day=${today}`);
  state.activeGoal = await fetchActiveGoal(state.person.id, today);
  render();
}

async function refreshReview(): Promise<void> {
  if (!state.person) {
    render();
    return;
  }
  state.weightTrend = await apiGet<WeightTrend>(`/api/weights/trend?person_id=${state.person.id}`);
  state.activeGoal = await fetchActiveGoal(state.person.id, today);
  state.week = await apiGet<WeekSummary>(
    `/api/summaries/week?person_id=${state.person.id}&start=2026-07-01&end=2026-07-07`
  );
  render();
}

async function refreshAllReadSurfaces(): Promise<void> {
  if (!state.person) {
    render();
    return;
  }
  state.summary = await apiGet<DaySummary>(`/api/diary/day?person_id=${state.person.id}&day=${today}`);
  state.weightTrend = await apiGet<WeightTrend>(`/api/weights/trend?person_id=${state.person.id}`);
  state.activeGoal = await fetchActiveGoal(state.person.id, today);
  state.week = await apiGet<WeekSummary>(
    `/api/summaries/week?person_id=${state.person.id}&start=2026-07-01&end=2026-07-07`
  );
  render();
}

async function hydrateStoredSession(): Promise<void> {
  const raw = localStorage.getItem(sessionStorageKey);
  if (!raw) return;
  try {
    const saved = JSON.parse(raw) as { household: Household; person_id: string | null };
    state.household = saved.household;
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
    JSON.stringify({ household: state.household, person_id: state.person?.id ?? null })
  );
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
      fat_g: fields.fat_g
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

function titleCase(value: string): string {
  return value.slice(0, 1).toUpperCase() + value.slice(1);
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
