import { expect, test } from "@playwright/test";

test("v1 daily driver workflow", async ({ page }) => {
  await page.goto("/");

  await page.locator("#setup-form input[name='household']").fill("Casa E2E");
  await page.locator("#setup-form input[name='name']").fill("Gabriel");
  await page.locator("#setup-form input[name='target_calories_kcal']").fill("2000");
  await page.locator("#setup-form input[name='target_protein_g']").fill("150");
  await page.locator("#setup-form button[type='submit']").click();
  await expect(page.getByText("Profile created.")).toBeVisible();
  await expect(page.locator(".profile-select").first()).toContainText("Gabriel");

  await page.locator("#add-person-form input[name='name']").fill("Ana");
  await page.locator("#add-person-form input[name='timezone']").fill("America/Sao_Paulo");
  await page.locator("#add-person-form button[type='submit']").click();
  await expect(page.getByText("Ana added.")).toBeVisible();
  await expect(page.locator(".profile-select").first()).toHaveValue(/person_/);

  await page.locator(".profile-select").first().selectOption({ label: "Gabriel" });
  await expect(page.getByText("Switched to Gabriel.")).toBeVisible();

  await page.locator("#food-form input[name='name']").fill("Queijo Minas");
  await page.locator("#food-form input[name='version_label']").fill("current");
  await page.locator("#food-form input[name='aliases']").fill("queijo, queijo minas");
  await page.locator("#food-form button[type='submit']").click();
  await expect(page.getByText(/Queijo Minas .* saved\./)).toBeVisible();

  await page.locator("#manual-log-form input[name='quantity']").fill("100");
  await page.locator("#manual-log-form button[type='submit']").click();
  await expect(page.getByText("Diary entry added.")).toBeVisible();
  await expect(page.getByText("315 kcal").first()).toBeVisible();

  await page.locator("#text-meal-form input[name='text']").fill("50g queijo");
  await page.locator("#text-meal-form input[name='external_lookup']").uncheck();
  await page.locator("#text-meal-form input[name='research_lookup']").uncheck();
  await page.locator("#text-meal-form button[type='submit']").click();
  await expect(page.getByText("Proposal drafted. Review before applying.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "draft", exact: true })).toBeVisible();
  await page.locator("#confirm-proposal").click();
  await expect(page.getByText("Proposal applied.")).toBeVisible();
  await expect(page.getByText("472.5").first()).toBeVisible();

  await page.locator("#label-scan-form input[name='barcode']").fill("7891000000000");
  await page.locator("#label-scan-form input[name='quantity_g']").fill("170");
  await page.locator("#label-scan-form button[type='submit']").click();
  await expect(page.getByText("Food version proposal drafted.")).toBeVisible();
  await expect(page.locator(".proposal").getByText("Iogurte Batavo Protein").first()).toBeVisible();
  await page.locator("#confirm-proposal").click();
  await expect(page.getByText("Proposal applied.")).toBeVisible();
  await expect(page.getByText("7891000000000").first()).toBeVisible();

  await page.locator("#agent-chat-form textarea[name='message']").fill("Why was 2026-07-02 high in calories?");
  await page.locator("#agent-chat-form input[name='background_job']").check();
  await page.locator("#agent-chat-form button[type='submit']").click();
  await expect(page.getByText("Agent chat queued for the worker.")).toBeVisible();
  await page.locator(".job-process").first().click();
  await expect(page.getByText("Job succeeded.")).toBeVisible();
  await page.locator(".job-open-chat").first().click();
  await expect(page.getByText("Loaded job chat answer.")).toBeVisible();
  await expect(page.locator(".chat-answer")).toContainText("explain_day");

  await page.locator(".profile-select").first().selectOption({ label: "Ana" });
  await expect(page.getByText("Switched to Ana.")).toBeVisible();
  await expect(page.getByText("No diary entries for this day yet.").first()).toBeVisible();

  await page.locator(".profile-select").first().selectOption({ label: "Gabriel" });
  await page.locator("#export-data").click();
  await expect(page.getByText("Export generated.")).toBeVisible();
  await expect(page.locator("#import-form textarea[name='import_json']")).toContainText("\"households\"");
});
