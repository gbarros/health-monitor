import { expect, test, type Page } from "@playwright/test";
import { Buffer } from "node:buffer";
import { existsSync, readFileSync } from "node:fs";
import { dirname, isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "..", "..");
const scenarioPath =
  process.env.CHATGPT_WEEK_SCENARIO ??
  resolve(here, "fixtures", "synthetic-week-scenario.json");

type WeekAction = {
  type: string;
  day: string;
  profile?: string;
  text?: string;
  message?: string;
  table_text?: string;
  barcode?: string;
  image?: string | null;
  quantity_g?: number;
  recipe_text?: string;
  weight_kg?: number;
};
type WeekScenario = {
  household: string;
  profiles: string[];
  actions: WeekAction[];
};

test("offline text meal survives reload and replays as a background job", async ({ page, context }) => {
  test.setTimeout(60_000);
  await setupHousehold(page);
  await seedReplayFood(page);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload();
  await page.evaluate(() => navigator.serviceWorker.ready);

  await context.setOffline(true);
  await goToPage(page, "Log");
  await sendLogMessage(page, "Meal note", "10am 50g Offline Replay Cheese", "Draft proposal");
  await expect(page.getByText("Meal note saved offline.")).toBeVisible();
  await expect(page.locator(".offline-list").getByText("pending")).toBeVisible();

  await page.reload();
  await expect(page.locator(".offline-list").getByText("Meal note")).toBeVisible();

  await context.setOffline(false);
  await page.locator("#replay-offline-outbox").click();
  await expect(page.locator(".offline-list").getByText("sent")).toBeVisible();
  await expect(backgroundJobRows(page).filter({ hasText: "Meal note" })).toHaveCount(1);

  await page.locator(".job-process").first().click();
  await expect(page.getByText("Job succeeded.")).toBeVisible();
  await page.locator(".job-load-proposal").first().click();
  await expect(page.getByText("Loaded job proposal.")).toBeVisible();
});

test("offline label scan persists upload and replays with attachment evidence", async ({ page, context }) => {
  test.setTimeout(60_000);
  await setupHousehold(page);
  await page.evaluate(() => navigator.serviceWorker.ready);

  await context.setOffline(true);
  await goToPage(page, "Log");
  await fillLabelScan(page, {
    table_text:
      "Produto: Iogurte Replay\nMarca: Synthetic\nPorcao: 170 g\nValor energetico: 120 kcal\nProteinas: 15 g\nCarboidratos: 10 g\nGorduras totais: 2 g",
    barcode: "7891000000001",
    quantity_g: 170,
    imageBuffer: Buffer.from("offline label image")
  });
  await expect(page.getByText("Product label saved offline.")).toBeVisible();
  await expect(page.locator(".offline-list").getByText("1 upload")).toBeVisible();

  await context.setOffline(false);
  await goToPage(page, "Work");
  await page.locator("#replay-offline-outbox").click();
  await expect(page.locator(".offline-list").getByText("sent")).toBeVisible();
  await page.locator(".job-process").first().click();
  await expect(page.getByText("Job succeeded.")).toBeVisible();
  await page.locator(".job-load-proposal").first().click();
  await expect(page.getByText("Loaded job proposal.")).toBeVisible();
  await expect(page.locator(".proposal")).toContainText("Iogurte Replay");
});

test("failed offline replay stays retryable and idempotent", async ({ page, context }) => {
  test.setTimeout(60_000);
  await setupHousehold(page);

  await context.setOffline(true);
  await goToPage(page, "Log");
  await sendLogMessage(page, "Chat", "Review this day later.", "Send");
  await expect(page.getByText("Agent chat saved offline.")).toBeVisible();
  await expect(page.locator(".offline-list").getByText("pending")).toBeVisible();

  await page.locator("#replay-offline-outbox").click();
  await expect(page.getByText("Waiting for connection before replaying offline notes.")).toBeVisible();
  await expect(page.locator(".offline-list").getByText("pending")).toBeVisible();

  await context.setOffline(false);
  await goToPage(page, "Work");
  await page.locator("#replay-offline-outbox").click();
  await expect(page.locator(".offline-list").getByText("sent")).toBeVisible();
  await page.locator("#replay-offline-outbox").click();
  await expect(backgroundJobRows(page).filter({ hasText: "Agent chat" })).toHaveCount(1);
});

test("synthetic week replay scenario completes through the app", async ({ page }) => {
  test.setTimeout(90_000);
  test.skip(!existsSync(scenarioPath), `Missing week scenario: ${scenarioPath}`);
  const scenario = JSON.parse(readFileSync(scenarioPath, "utf-8")) as WeekScenario;

  for (const action of scenario.actions) {
    await runWeekAction(page, scenario, action);
  }

  await expect(page.locator(".profile-select").first()).toHaveValue(/person_/);
  await goToPage(page, "Review");
  await expect(page.locator(".weight-chart")).toBeVisible();
});

async function runWeekAction(page: Page, scenario: WeekScenario, action: WeekAction): Promise<void> {
  if (action.type === "setup_household") {
    await setupHousehold(page, scenario.household, scenario.profiles);
    return;
  }
  await setSelectedDay(page, action.day);
  if (action.type === "switch_profile") {
    await page.locator(".profile-select").first().selectOption({ label: action.profile ?? scenario.profiles[0] });
    await expect(page.getByText(new RegExp(`Switched to ${action.profile ?? scenario.profiles[0]}`))).toBeVisible();
    return;
  }
  if (action.type === "label_scan") {
    await goToPage(page, "Log");
    await fillLabelScan(page, {
      table_text: action.table_text ?? "",
      barcode: action.barcode ?? "",
      quantity_g: action.quantity_g ?? 100,
      imagePath: action.image ?? null
    });
    await expect(page.getByText(/Food version proposal drafted/)).toBeVisible();
    return;
  }
  if (action.type === "text_meal") {
    await goToPage(page, "Log");
    await sendLogMessage(page, "Meal note", action.text ?? "", "Draft proposal");
    await expect(page.getByText(/Proposal drafted|saved offline|needs clarification/).first()).toBeVisible();
    return;
  }
  if (action.type === "recipe") {
    await goToPage(page, "Log");
    await sendLogMessage(page, "Recipe", `${action.recipe_text ?? ""}\nLog grams: ${action.quantity_g ?? 100} g`, "Draft proposal");
    await expect(page.getByText("Recipe proposal drafted.")).toBeVisible();
    return;
  }
  if (action.type === "chat_question" || action.type === "correction_request" || action.type === "review_note_request") {
    await goToPage(page, "Log");
    await sendLogMessage(page, "Chat", action.message ?? "", "Send");
    await expect(page.getByText("Agent chat queued for the worker.")).toBeVisible();
    await goToPage(page, "Work");
    await page.locator(".job-process").first().click();
    await expect(page.getByText("Job succeeded.")).toBeVisible();
    await page.locator(".job-open-chat").first().click();
    await expect(page.getByText("Loaded job chat answer.")).toBeVisible();
    return;
  }
  if (action.type === "weight_entry") {
    await goToPage(page, "Diary");
    await page.locator("#weight-form input[name='weight_kg']").fill(String(action.weight_kg ?? 91));
    await page.locator("#weight-form button[type='submit']").click();
    await expect(page.getByText("Weight added.")).toBeVisible();
    return;
  }
  if (action.type === "confirm_latest_proposal") {
    await goToPage(page, "Log");
    const confirm = page.locator("#confirm-proposal");
    if (await confirm.isVisible()) {
      await confirm.click();
      await expect(page.getByText("Proposal applied.")).toBeVisible();
    } else {
      await page.locator("#reject-proposal").click();
      await expect(page.getByText("Proposal rejected.")).toBeVisible();
    }
    return;
  }
  if (action.type === "expect_day_totals") {
    await goToPage(page, "Diary");
    await expect(page.getByText("kcal").first()).toBeVisible();
  }
}

async function setupHousehold(
  page: Page,
  household = "Casa E2E",
  profiles = ["Person A", "Person B"]
): Promise<void> {
  await page.goto("/");
  await page.locator("#setup-form input[name='household']").fill(household);
  await page.locator("#setup-form input[name='name']").fill(profiles[0]);
  await page.locator("#setup-form input[name='target_calories_kcal']").fill("2000");
  await page.locator("#setup-form input[name='target_protein_g']").fill("150");
  await page.locator("#setup-form button[type='submit']").click();
  await expect(page.getByText("Profile created.")).toBeVisible();

  if (profiles[1]) {
    await goToPage(page, "Settings");
    await page.locator("#add-person-form input[name='name']").fill(profiles[1]);
    await page.locator("#add-person-form button[type='submit']").click();
    await expect(page.getByText(`${profiles[1]} added.`)).toBeVisible();
    await page.locator(".profile-select").first().selectOption({ label: profiles[0] });
    await expect(page.getByText(`Switched to ${profiles[0]}.`)).toBeVisible();
  }
}

async function seedReplayFood(page: Page): Promise<void> {
  await goToPage(page, "Library");
  await page.locator("#food-form input[name='name']").fill("Offline Replay Cheese");
  await page.locator("#food-form input[name='aliases']").fill("offline replay cheese");
  await page.locator("#food-form button[type='submit']").click();
  await expect(page.getByText(/Offline Replay Cheese .* saved\./)).toBeVisible();
}

async function goToPage(page: Page, name: string): Promise<void> {
  await page.getByRole("link", { name }).click();
  await expect(page.getByRole("link", { name })).toHaveAttribute("aria-current", "page");
}

async function setSelectedDay(page: Page, day: string): Promise<void> {
  await goToPage(page, "Diary");
  if ((await page.locator("#selected-day").inputValue()) === day) {
    return;
  }
  await page.locator("#selected-day").fill(day);
  await page.locator("#selected-day").dispatchEvent("change");
  await expect(page.getByText(new RegExp(`(Loaded|Showing) ${day}\\.`))).toBeVisible();
}

async function fillLabelScan(
  page: Page,
  options: {
    table_text: string;
    barcode: string;
    quantity_g: number;
    imagePath?: string | null;
    imageBuffer?: Buffer;
  }
): Promise<void> {
  await selectLogMode(page, "Product label");
  if (options.imagePath) {
    const imagePath = isAbsolute(options.imagePath) ? options.imagePath : resolve(repoRoot, options.imagePath);
    await agentChat(page).getByLabel("Add files").setInputFiles(imagePath);
  } else {
    await agentChat(page).getByLabel("Add files").setInputFiles({
      name: "synthetic-label.png",
      mimeType: "image/png",
      buffer: options.imageBuffer ?? Buffer.from("synthetic label image")
    });
  }
  await sendCurrentLogMessage(
    page,
    `${options.table_text}
Barcode: ${options.barcode}
Quantity: ${options.quantity_g} g`,
    "Draft proposal"
  );
}

function agentChat(page: Page) {
  return page.locator("#log-agent-chat");
}

async function selectLogMode(page: Page, mode: string): Promise<void> {
  await agentChat(page).getByRole("tab", { name: new RegExp(mode) }).click();
}

async function sendLogMessage(
  page: Page,
  mode: string,
  text: string,
  button: "Send" | "Draft proposal"
): Promise<void> {
  await selectLogMode(page, mode);
  await sendCurrentLogMessage(page, text, button);
}

async function sendCurrentLogMessage(
  page: Page,
  text: string,
  button: "Send" | "Draft proposal"
): Promise<void> {
  const chat = agentChat(page);
  await chat.getByRole("textbox", { name: "Message" }).fill(text);
  await chat.getByRole("button", { name: button, exact: true }).click();
}

function backgroundJobRows(page: Page) {
  return page
    .locator("section.today")
    .filter({ has: page.getByRole("heading", { name: "Background jobs" }) })
    .locator(".job-list > li");
}
