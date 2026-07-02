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
  await page.locator("#text-meal-form input[name='text']").fill("10am 50g Offline Replay Cheese");
  await page.locator("#text-meal-form button[type='submit']").click();
  await expect(page.getByText("Text meal saved offline.")).toBeVisible();
  await expect(page.locator(".offline-list").getByText("pending")).toBeVisible();

  await page.reload();
  await expect(page.locator(".offline-list").getByText("Text meal")).toBeVisible();

  await context.setOffline(false);
  await page.locator("#replay-offline-outbox").click();
  await expect(page.locator(".offline-list").getByText("sent")).toBeVisible();
  await expect(backgroundJobRows(page).filter({ hasText: "Text meal" })).toHaveCount(1);

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
  await fillLabelScan(page, {
    table_text:
      "Produto: Iogurte Replay\nMarca: Synthetic\nPorcao: 170 g\nValor energetico: 120 kcal\nProteinas: 15 g\nCarboidratos: 10 g\nGorduras totais: 2 g",
    barcode: "7891000000001",
    quantity_g: 170,
    imageBuffer: Buffer.from("offline label image")
  });
  await page.locator("#label-scan-form button[type='submit']").click();
  await expect(page.getByText("Label scan saved offline.")).toBeVisible();
  await expect(page.locator(".offline-list").getByText("1 upload")).toBeVisible();

  await context.setOffline(false);
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
  await page.locator("#agent-chat-form textarea[name='message']").fill("Review this day later.");
  await page.locator("#agent-chat-form button[type='submit']").click();
  await expect(page.getByText("Agent chat saved offline.")).toBeVisible();
  await expect(page.locator(".offline-list").getByText("pending")).toBeVisible();

  await page.locator("#replay-offline-outbox").click();
  await expect(page.getByText("Waiting for connection before replaying offline notes.")).toBeVisible();
  await expect(page.locator(".offline-list").getByText("pending")).toBeVisible();

  await context.setOffline(false);
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
    await fillLabelScan(page, {
      table_text: action.table_text ?? "",
      barcode: action.barcode ?? "",
      quantity_g: action.quantity_g ?? 100,
      imagePath: action.image ?? null
    });
    await page.locator("#label-scan-form button[type='submit']").click();
    await expect(page.getByText(/Food version proposal drafted/)).toBeVisible();
    return;
  }
  if (action.type === "text_meal") {
    await page.locator("#text-meal-form input[name='text']").fill(action.text ?? "");
    await page.locator("#text-meal-form input[name='external_lookup']").uncheck();
    await page.locator("#text-meal-form input[name='research_lookup']").uncheck();
    await page.locator("#text-meal-form button[type='submit']").click();
    await expect(page.getByText(/Proposal drafted|saved offline|needs clarification/).first()).toBeVisible();
    return;
  }
  if (action.type === "recipe") {
    await page.locator("#recipe-form input[name='quantity_g']").fill(String(action.quantity_g ?? 100));
    await page.locator("#recipe-form textarea[name='recipe_text']").fill(action.recipe_text ?? "");
    await page.locator("#recipe-form button[type='submit']").click();
    await expect(page.getByText("Recipe proposal drafted.")).toBeVisible();
    return;
  }
  if (action.type === "chat_question" || action.type === "correction_request" || action.type === "review_note_request") {
    await page.locator("#agent-chat-form textarea[name='message']").fill(action.message ?? "");
    await page.locator("#agent-chat-form input[name='background_job']").check();
    await page.locator("#agent-chat-form button[type='submit']").click();
    await expect(page.getByText("Agent chat queued for the worker.")).toBeVisible();
    await page.locator(".job-process").first().click();
    await expect(page.getByText("Job succeeded.")).toBeVisible();
    await page.locator(".job-open-chat").first().click();
    await expect(page.getByText("Loaded job chat answer.")).toBeVisible();
    return;
  }
  if (action.type === "weight_entry") {
    await page.locator("#weight-form input[name='weight_kg']").fill(String(action.weight_kg ?? 91));
    await page.locator("#weight-form button[type='submit']").click();
    await expect(page.getByText("Weight added.")).toBeVisible();
    return;
  }
  if (action.type === "confirm_latest_proposal") {
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
    await page.locator("#add-person-form input[name='name']").fill(profiles[1]);
    await page.locator("#add-person-form button[type='submit']").click();
    await expect(page.getByText(`${profiles[1]} added.`)).toBeVisible();
    await page.locator(".profile-select").first().selectOption({ label: profiles[0] });
    await expect(page.getByText(`Switched to ${profiles[0]}.`)).toBeVisible();
  }
}

async function seedReplayFood(page: Page): Promise<void> {
  await page.locator("#food-form input[name='name']").fill("Offline Replay Cheese");
  await page.locator("#food-form input[name='aliases']").fill("offline replay cheese");
  await page.locator("#food-form button[type='submit']").click();
  await expect(page.getByText(/Offline Replay Cheese .* saved\./)).toBeVisible();
}

async function setSelectedDay(page: Page, day: string): Promise<void> {
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
  await page.locator("#label-scan-form textarea[name='table_text']").fill(options.table_text);
  await page.locator("#label-scan-form input[name='barcode']").fill(options.barcode);
  await page.locator("#label-scan-form input[name='quantity_g']").fill(String(options.quantity_g));
  if (options.imagePath) {
    const imagePath = isAbsolute(options.imagePath) ? options.imagePath : resolve(repoRoot, options.imagePath);
    await page.locator("#label-scan-form input[name='attachment']").setInputFiles(imagePath);
  } else {
    await page.locator("#label-scan-form input[name='attachment']").setInputFiles({
      name: "synthetic-label.png",
      mimeType: "image/png",
      buffer: options.imageBuffer ?? Buffer.from("synthetic label image")
    });
  }
}

function backgroundJobRows(page: Page) {
  return page
    .locator("section.today")
    .filter({ has: page.getByRole("heading", { name: "Background jobs" }) })
    .locator(".job-list > li");
}
