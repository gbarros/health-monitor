import { expect, test } from "@playwright/test";
import { Buffer } from "node:buffer";

test("v1 daily driver workflow", async ({ page }) => {
  await page.goto("/");

  await page.locator("#onboarding-message-form textarea[name='message']").fill(
    "Household: Casa E2E\nName: Gabriel\nTimezone: America/Sao_Paulo\nTargets: 2000 kcal, 150g protein"
  );
  await page.locator("#onboarding-message-form button[type='submit']").click();
  await expect(page.getByText("Profile created.")).toBeVisible();
  await expect(page.locator(".profile-select").first()).toContainText("Gabriel");

  await goToPage(page, "Settings");
  await page.locator("#add-person-form input[name='name']").fill("Ana");
  await page.locator("#add-person-form input[name='timezone']").fill("America/Sao_Paulo");
  await page.locator("#add-person-form button[type='submit']").click();
  await expect(page.getByText("Ana added.")).toBeVisible();
  await expect(page.locator(".profile-select").first()).toHaveValue(/person_/);

  await page.locator(".profile-select").first().selectOption({ label: "Gabriel" });
  await expect(page.getByText("Switched to Gabriel.")).toBeVisible();

  await goToPage(page, "Log");
  await agentChat(page).getByRole("textbox", { name: "Message" }).fill("Still typing\n- do not erase");
  await goToPage(page, "Work");
  await goToPage(page, "Log");
  await expect(agentChat(page).getByRole("textbox", { name: "Message" })).toHaveValue("Still typing\n- do not erase");
  await agentChat(page).getByRole("textbox", { name: "Message" }).clear();

  await goToPage(page, "Library");
  await page.locator("#food-form input[name='name']").fill("Queijo Minas");
  await page.locator("#food-form input[name='version_label']").fill("current");
  await page.locator("#food-form input[name='aliases']").fill("queijo, queijo minas");
  await page.locator("#food-form button[type='submit']").click();
  await expect(page.getByText(/Queijo Minas .* saved\./)).toBeVisible();

  await goToPage(page, "Diary");
  await page.locator("#manual-log-form input[name='quantity']").fill("100");
  await page.locator("#manual-log-form button[type='submit']").click();
  await expect(page.getByText("Diary entry added.")).toBeVisible();
  await expect(page.getByText("315 kcal").first()).toBeVisible();

  await page.locator(".entry-edit-form input[name='quantity_g']").first().fill("80");
  await page.locator(".entry-edit-form button[type='submit']").first().click();
  await expect(page.getByText("Diary entry updated.")).toBeVisible();
  await expect(page.getByText("252 kcal").first()).toBeVisible();

  await goToPage(page, "Log");
  await sendLogMessage(page, "Meal note", "50g queijo", "Draft proposal");
  await expect(page.getByText("Proposal drafted. Review before applying.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "draft", exact: true })).toBeVisible();
  await page.locator("#confirm-proposal").click();
  await expect(page.getByText("Proposal applied.")).toBeVisible();
  await goToPage(page, "Diary");
  await expect(page.getByText("409.5").first()).toBeVisible();

  await goToPage(page, "Log");
  await selectLogMode(page, "Product label");
  await page.evaluate(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: async () => new MediaStream()
      }
    });
    window.HTMLMediaElement.prototype.play = async () => undefined;
    class MockBarcodeDetector {
      async detect() {
        return [{ rawValue: "7891000000999" }];
      }
    }
    Object.defineProperty(window, "BarcodeDetector", { configurable: true, value: MockBarcodeDetector });
  });
  await agentChat(page).getByRole("button", { name: "Scan code" }).click();
  await expect(agentChat(page).getByRole("textbox", { name: "Message" })).toHaveValue("Barcode: 7891000000999");
  await agentChat(page).getByRole("textbox", { name: "Message" }).clear();
  await agentChat(page).getByLabel("Add files").setInputFiles({
    name: "label.png",
    mimeType: "image/png",
    buffer: Buffer.from("fake png label evidence")
  });
  await sendCurrentLogMessage(
    page,
    `Product: Iogurte Batavo Protein
Brand: Batavo
Barcode: 7891000000000
Quantity: 170 g
Serving: 170 g
Calories: 120 kcal
Protein: 15 g
Carbs: 10 g
Fat: 2 g`,
    "Draft proposal"
  );
  await expect(page.getByText("Food version proposal drafted with 1 attachment.")).toBeVisible();
  await expect(page.locator(".proposal").getByText("Iogurte Batavo Protein").first()).toBeVisible();
  await page.locator("#confirm-proposal").click();
  await expect(page.getByText("Proposal applied.")).toBeVisible();
  await expect(page.getByText("7891000000000").first()).toBeVisible();

  await sendLogMessage(
    page,
    "Recipe",
    `Recipe: Queijo batch
Yield: 1000 g
Ingredients:
1000g queijo
Log grams: 100 g`,
    "Draft proposal"
  );
  await expect(page.getByText("Recipe proposal drafted.")).toBeVisible();
  await expect(page.locator(".proposal").getByText("Queijo batch").first()).toBeVisible();
  await page.locator("#confirm-proposal").click();
  await expect(page.getByText("Proposal applied.")).toBeVisible();

  await goToPage(page, "Diary");
  await page.locator("#weight-form input[name='weight_kg']").fill("91.2");
  await page.locator("#weight-form button[type='submit']").click();
  await expect(page.getByText("Weight added.")).toBeVisible();
  await goToPage(page, "Review");
  await expect(page.getByText("91.2 kg").first()).toBeVisible();
  await expect(page.locator(".weight-chart")).toBeVisible();
  await page.locator(".weight-edit-form input[name='weight_kg']").first().fill("90.9");
  await page.locator(".weight-edit-form button[type='submit']").first().click();
  await expect(page.getByText("Weight updated.")).toBeVisible();
  await expect(page.getByText("90.9 kg").first()).toBeVisible();

  await goToPage(page, "Log");
  await sendLogMessage(page, "Chat", "Why was 2026-07-02 high in calories?", "Send");
  await expect(page.getByText("Agent chat answered from app data.")).toBeVisible();
  await expect(agentChat(page)).toContainText("explain_day");
  await sendLogMessage(page, "Chat", "What was my protein total on 2026-07-02?", "Send");
  await expect(page.getByText("Agent chat answered from app data.")).toBeVisible();
  await page.getByRole("button", { name: /Why was 2026-07-02 high in calories/ }).click();
  await expect(page.getByText("Loaded previous chat turn.")).toBeVisible();
  await expect(agentChat(page)).toContainText("Why was 2026-07-02 high in calories?");

  await goToPage(page, "Log");
  await sendLogMessage(page, "Correction", "Change queijo on 2026-07-02 to 60g", "Send");
  await expect(page.getByText("Correction drafted a proposal. Review before applying.")).toBeVisible();
  await expect(page.locator(".proposal").getByText("Update")).toBeVisible();
  await expect(agentChat(page)).toContainText("draft_diary_correction");

  await goToPage(page, "Log");
  await sendLogMessage(
    page,
    "Review note",
    "Save review note for 2026-07-01 to 2026-07-07: Social dinners made adherence harder.",
    "Send"
  );
  await expect(page.getByText("Review note drafted a proposal. Review before applying.")).toBeVisible();
  await expect(page.locator(".proposal").getByText("Draft Review Note", { exact: true })).toBeVisible();
  await expect(agentChat(page)).toContainText("draft_review_note");

  await page.locator(".profile-select").first().selectOption({ label: "Ana" });
  await expect(page.locator(".topbar-subtitle")).toContainText("Ana");
  await goToPage(page, "Diary");
  await expect(page.getByText("No diary entries for this day yet.").first()).toBeVisible();

  await page.locator(".profile-select").first().selectOption({ label: "Gabriel" });
  await page.locator(".entry-delete").first().click();
  await expect(page.getByText("Diary entry deleted.")).toBeVisible();
  await page.locator("#undo-delete").click();
  await expect(page.getByText(/Restored .* g entry\./)).toBeVisible();

  await goToPage(page, "Settings");
  await page.locator("#export-data").click();
  await expect(page.getByText("Export generated.")).toBeVisible();
  await expect(page.locator("#import-form textarea[name='import_json']")).toContainText("\"households\"");
  await page.locator("#import-form button[type='submit']").click();
  await expect(page.getByText("import target must be empty")).toBeVisible();
});

async function goToPage(page: import("@playwright/test").Page, name: string): Promise<void> {
  await page.getByRole("link", { name }).click();
  await expect(page.getByRole("link", { name })).toHaveAttribute("aria-current", "page");
}

function agentChat(page: import("@playwright/test").Page) {
  return page.locator("#log-agent-chat");
}

async function selectLogMode(page: import("@playwright/test").Page, mode: string): Promise<void> {
  await agentChat(page).getByRole("tab", { name: new RegExp(mode) }).click();
}

async function sendLogMessage(
  page: import("@playwright/test").Page,
  mode: string,
  text: string,
  button: "Send" | "Draft proposal"
): Promise<void> {
  await selectLogMode(page, mode);
  await sendCurrentLogMessage(page, text, button);
}

async function sendCurrentLogMessage(
  page: import("@playwright/test").Page,
  text: string,
  button: "Send" | "Draft proposal"
): Promise<void> {
  const chat = agentChat(page);
  await chat.getByRole("textbox", { name: "Message" }).fill(text);
  await chat.getByRole("button", { name: button, exact: true }).click();
}
