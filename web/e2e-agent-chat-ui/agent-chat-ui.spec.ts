import { expect, test } from "@playwright/test";
import { Buffer } from "node:buffer";

test("renders the demo thread and switches modes", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Agent Chat UI" })).toBeVisible();
  await expect(page.getByRole("tab", { name: /Chat/ })).toHaveAttribute("aria-selected", "true");

  await page.getByRole("tab", { name: /Evidence/ }).click();
  await expect(page.getByRole("tab", { name: /Evidence/ })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByPlaceholder("Describe what the attached files should prove...")).toBeFocused();

  const lastEvent = page.locator("#last-event");
  await expect(lastEvent).toContainText("agent-chat:mode-change");
  await expect(lastEvent).toContainText("evidence");
});

test("sends multiline text with multiple attachments", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("tab", { name: /Capture/ }).click();
  await page.getByLabel("Add files").setInputFiles([
    {
      name: "first.png",
      mimeType: "image/png",
      buffer: Buffer.from("fake image one")
    },
    {
      name: "second.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("fake text")
    }
  ]);
  await expect(page.getByText("first.png")).toBeVisible();
  await expect(page.getByText("second.txt")).toBeVisible();

  await page.getByRole("textbox", { name: "Message" }).fill("First line\n- item one\n- item two");
  await page.getByRole("button", { name: "Send", exact: true }).click();

  const event = await lastEvent(page);
  expect(event.name).toBe("agent-chat:send");
  expect(event.detail.modeId).toBe("capture");
  expect(event.detail.text).toBe("First line\n- item one\n- item two");
  expect(event.detail.clientRequestId).toMatch(/[0-9a-f-]{10,}/);
  expect(event.detail.attachments.map((attachment: { name: string }) => attachment.name)).toEqual([
    "first.png",
    "second.txt"
  ]);
  await expect(page.locator("[data-message-id]").last()).toContainText("First line");
});

test("removes attachments and emits the generic remove event", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Add files").setInputFiles({
    name: "remove-me.png",
    mimeType: "image/png",
    buffer: Buffer.from("fake")
  });
  await expect(page.getByText("remove-me.png")).toBeVisible();

  await page.getByRole("button", { name: "Remove remove-me.png" }).click();
  await expect(page.getByText("remove-me.png")).toHaveCount(0);

  const event = await lastEvent(page);
  expect(event.name).toBe("agent-chat:remove-attachment");
  expect(event.detail.attachmentId).toMatch(/^local_/);
});

test("preserves draft text across host data refreshes", async ({ page }) => {
  await page.goto("/");
  const textbox = page.getByRole("textbox", { name: "Message" });
  await textbox.fill("Still typing\n- item");

  await page.getByRole("button", { name: "Queued" }).click();

  await expect(textbox).toHaveValue("Still typing\n- item");
});

test("shows statuses, tool calls, draft actions, retry, cancel, and inspect events", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Read context")).toBeVisible();
  await expect(page.getByText("Extract evidence")).toBeVisible();
  await expect(page.getByText("Draft proposal")).toBeVisible();
  await expect(page.getByText("External lookup")).toBeVisible();

  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.locator("#last-event")).toContainText("agent-chat:confirm-draft");

  await page.getByRole("button", { name: "Reject" }).click();
  await expect(page.locator("#last-event")).toContainText("agent-chat:reject-draft");

  await page.getByRole("button", { name: "Failed" }).click();
  await expect(page.getByRole("status")).toContainText("Failed");
  await page.getByRole("button", { name: "Retry" }).first().click();
  await expect(page.locator("#last-event")).toContainText("agent-chat:retry");

  await page.getByRole("button", { name: "Sending" }).click();
  await expect(page.getByRole("status")).toContainText("Sending");
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.locator("#last-event")).toContainText("agent-chat:cancel");

  await page.getByRole("button", { name: "Inspect prompt" }).click();
  await expect(page.locator("#last-event")).toContainText("agent-chat:inspect-prompt");

  await page.getByRole("button", { name: "Idle" }).click();
  await page.getByRole("button", { name: "Sample action" }).click();
  const actionEvent = await lastEvent(page);
  expect(actionEvent.name).toBe("agent-chat:composer-action");
  expect(actionEvent.detail.actionId).toBe("sample-action");
  expect(actionEvent.detail.modeId).toBe("chat");
});

test("keeps keyboard order and mobile layout usable", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Idle" })).toBeFocused();

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("agent-chat")).toBeVisible();
  const hasHorizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(hasHorizontalOverflow).toBe(false);

  const sendBox = await page.getByRole("button", { name: "Send", exact: true }).boundingBox();
  expect(sendBox?.height).toBeGreaterThanOrEqual(44);

  await page.getByRole("textbox", { name: "Message" }).fill("Keyboard path\n- line");
  await page.keyboard.press(process.platform === "darwin" ? "Meta+Enter" : "Control+Enter");
  await expect(page.locator("#last-event")).toContainText("agent-chat:send");
});

test("captures desktop and mobile screenshot smoke samples", async ({ page }) => {
  await page.goto("/");
  const desktop = await page.locator("agent-chat").screenshot();
  expect(desktop.length).toBeGreaterThan(10_000);

  await page.setViewportSize({ width: 390, height: 844 });
  const mobile = await page.locator("agent-chat").screenshot();
  expect(mobile.length).toBeGreaterThan(10_000);
});

async function lastEvent(page: import("@playwright/test").Page): Promise<{
  name: string;
  detail: Record<string, any>;
}> {
  return page.evaluate(() => {
    const events = window.__agentChatEvents as Array<{ name: string; detail: Record<string, any> }>;
    return events.at(-1);
  });
}
