import { expect, test, type Page } from "@playwright/test";

test.use({ viewport: { width: 375, height: 812 } });

test("phase 1 mobile shell logs a meal and updates the day card", async ({ page }) => {
  await createFirstProfile(page, "Gabriel");
  const card = dayCard(page);

  await expect(page.getByRole("heading", { name: "Diário" })).toBeVisible();
  await expect(page.getByLabel("Selecionar perfil")).toContainText("Gabriel");
  await expect(card).toContainText("Restante:");
  await expect(card.getByLabel("Macronutrientes do dia")).toContainText("Fibra");
  await expect(page.getByLabel("Ações rápidas")).toContainText("Registrar refeição");
  await expect(composer(page)).toBeVisible();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);

  const ids = await storedIds(page);
  await page.request.post("/api/foods", {
    data: {
      household_id: ids.householdId,
      name: "Queijo Minas E2E",
      brand: "E2E",
      version_label: "current",
      source: "manual_e2e",
      nutrients_per_100g: {
        calories_kcal: 315,
        protein_g: 22,
        carbs_g: 3,
        fat_g: 24,
        fiber_g: 0,
        sodium_mg: 520,
      },
      aliases: ["queijo minas e2e"],
    },
  });

  await page.getByLabel("Ações rápidas").getByRole("button", { name: "Registrar refeição" }).click();
  await composer(page).fill("100g Queijo Minas E2E");
  await page.getByRole("button", { name: "Enviar", exact: true }).click();

  await expect(page.getByText("Rascunhei a refeição.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Confirmar" }).last()).toBeVisible();
  await page.getByRole("button", { name: "Confirmar" }).last().click();

  await expect(card).toContainText("315 kcal");
  await expect(card).toContainText("Queijo Minas E2E");
  await expect(card).toContainText("E2E");
});

test("phase 1 chat history hydrates after reload without duplicating the reply", async ({ page }) => {
  await createFirstProfile(page, "Ana");

  await composer(page).fill("Can you alter my profile and goals?");
  await page.getByRole("button", { name: "Enviar", exact: true }).click();
  await expect(page.getByText("I can help change profile fields and nutrition goals")).toBeVisible();

  await page.reload();
  await expect(page.getByText("Can you alter my profile and goals?")).toHaveCount(1);
  await expect(page.getByText("I can help change profile fields and nutrition goals")).toHaveCount(1);
});

test("phase 3 chat-first shell records weight without selecting a mode", async ({ page }) => {
  await createFirstProfile(page, "Clara");

  await expect(page.getByText("CURRENT MODE")).toHaveCount(0);
  await composer(page).fill("amanheci com 96,3kgs");
  await page.getByRole("button", { name: "Enviar", exact: true }).click();

  await expect(page.getByText("Registrei o peso de 96.3 kg para hoje.")).toBeVisible();
  await expect(dayCard(page)).toContainText("96,3 kg");
});

test("phase 2 follow-up meal note amends the open proposal before confirmation", async ({ page }) => {
  await createFirstProfile(page, "Bruno");
  const ids = await storedIds(page);
  await seedFood(page, ids.householdId, {
    name: "Arroz E2E",
    version_label: "cozido",
    nutrients_per_100g: { calories_kcal: 130, protein_g: 2.7, carbs_g: 28, fat_g: 0.3 },
    aliases: ["arroz e2e"],
  });
  await seedFood(page, ids.householdId, {
    name: "Feijao E2E",
    version_label: "cozido",
    nutrients_per_100g: { calories_kcal: 76, protein_g: 4.8, carbs_g: 13.6, fat_g: 0.5 },
    aliases: ["feijao e2e", "feijão e2e"],
  });
  await seedFood(page, ids.householdId, {
    name: "Frango E2E",
    version_label: "grelhado",
    nutrients_per_100g: { calories_kcal: 165, protein_g: 31, carbs_g: 0, fat_g: 3.6 },
    aliases: ["frango e2e"],
  });

  await page.getByLabel("Ações rápidas").getByRole("button", { name: "Registrar refeição" }).click();
  await composer(page).fill("Almoço:\n150g Arroz E2E\n100g Feijao E2E");
  await page.getByRole("button", { name: "Enviar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "2 diary entries drafted from text meal" })).toBeVisible();

  await composer(page).fill("esqueci 113g de Frango E2E");
  await page.getByRole("button", { name: "Enviar", exact: true }).click();

  await expect(page.getByRole("heading", { name: "3 diary entries drafted after meal amendment" })).toBeVisible();
  await expect(page.getByText("Frango E2E", { exact: true })).toBeVisible();
  await expect(page.getByText("Substituída")).toBeVisible();
  await page.getByRole("button", { name: "Confirmar" }).last().click();

  const card = dayCard(page);
  await expect(card).toContainText("Arroz E2E");
  await expect(card).toContainText("Feijao E2E");
  await expect(card).toContainText("Frango E2E");
});

async function createFirstProfile(page: Page, personName: string): Promise<void> {
  await page.goto("/");
  await page.getByLabel("Sua mensagem").fill(
    [
      "Casa: Casa E2E",
      `Nome: ${personName}`,
      "Fuso: America/Sao_Paulo",
      "2000 kcal, 150g proteína, 180g carboidratos, 70g gordura, 30g fibra, 2300mg sódio",
      "Atividade: moderada",
    ].join("\n"),
  );
  await page.getByRole("button", { name: "Criar primeiro perfil" }).click();
  await expect(page.getByRole("heading", { name: "Diário" })).toBeVisible();
}

function composer(page: Page) {
  return page.getByPlaceholder("Escreva uma refeição, pergunta, correção ou cole uma tabela...");
}

function dayCard(page: Page) {
  return page.locator(".chat-column .day-card");
}

async function storedIds(page: Page): Promise<{ householdId: string; personId: string }> {
  const ids = await page.evaluate(() => ({
    householdId: window.localStorage.getItem("health-monitor.household-id"),
    personId: window.localStorage.getItem("health-monitor.person-id"),
  }));
  if (!ids.householdId || !ids.personId) {
    throw new Error("Expected onboarding to store household and person ids");
  }
  return { householdId: ids.householdId, personId: ids.personId };
}

async function seedFood(
  page: Page,
  householdId: string,
  food: {
    name: string;
    version_label: string;
    nutrients_per_100g: Record<string, number>;
    aliases: string[];
  },
): Promise<void> {
  await page.request.post("/api/foods", {
    data: {
      household_id: householdId,
      brand: "E2E",
      source: "manual_e2e",
      ...food,
    },
  });
}
