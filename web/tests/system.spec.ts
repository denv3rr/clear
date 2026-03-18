import { expect, test, type Page } from "@playwright/test";

async function waitForConfirmOrMessage(page: Page, message: string) {
  await expect
    .poll(async () => {
      if (await page.getByRole("button", { name: "Confirm" }).count()) {
        return "confirm";
      }
      if (await page.getByText(message).count()) {
        return "message";
      }
      return "pending";
    })
    .toMatch(/confirm|message/);
}

test("system maintenance flows require explicit confirmation and fail safely", async ({ page }) => {
  const bodies: Record<string, unknown> = {};
  await page.route("**/api/maintenance/normalize-lots", async (route) => {
    bodies.normalize = route.request().postDataJSON();
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Service unavailable" })
    });
  });
  await page.route("**/api/maintenance/clear-report-cache", async (route) => {
    bodies.clearCache = route.request().postDataJSON();
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Service unavailable" })
    });
  });
  await page.route("**/api/maintenance/cleanup-orphans", async (route) => {
    bodies.cleanupOrphans = route.request().postDataJSON();
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Service unavailable" })
    });
  });
  await page.route("**/api/clients/duplicates/cleanup", async (route) => {
    bodies.cleanupDuplicates = route.request().postDataJSON();
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Service unavailable" })
    });
  });

  await page.goto("/system");
  await expect(page.getByText("System Settings & Diagnostics")).toBeVisible();

  await page.getByRole("button", { name: "Normalize Lot Timestamps" }).click();
  await expect(
    page.getByText("This action cannot be undone. Confirm only if you have recent backups.")
  ).toBeVisible();
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByText("API 503")).toBeVisible();
  expect(bodies.normalize).toMatchObject({ confirm: true });

  await page.getByRole("button", { name: "Clear Report Cache" }).click();
  await expect(
    page.getByText("This action cannot be undone. Confirm only if you have recent backups.")
  ).toBeVisible();
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByText("API 503")).toBeVisible();
  expect(bodies.clearCache).toMatchObject({ confirm: true });

  const orphanEmptyMessage = "No orphaned holdings or lots detected.";
  await page.getByRole("button", { name: "Remove Orphaned Holdings/Lots" }).click();
  await waitForConfirmOrMessage(page, orphanEmptyMessage);
  if (await page.getByRole("button", { name: "Confirm" }).count()) {
    await page.getByRole("button", { name: "Confirm" }).click();
    await expect(page.getByText("API 503")).toBeVisible();
    expect(bodies.cleanupOrphans).toMatchObject({ confirm: true });
  } else {
    await expect(page.getByText(orphanEmptyMessage)).toBeVisible();
    expect(bodies.cleanupOrphans).toBeUndefined();
  }

  const duplicateButton = page.getByRole("button", { name: "Remove duplicates" });
  if (await duplicateButton.count()) {
    await duplicateButton.click();
    await expect(
      page.getByText("This action cannot be undone. Confirm only if you have recent backups.")
    ).toBeVisible();
    await page.getByRole("button", { name: "Confirm" }).click();
    await expect(page.getByText("API 503")).toBeVisible();
    expect(bodies.cleanupDuplicates).toMatchObject({ confirm: true });
  } else {
    await expect(duplicateButton).toHaveCount(0);
    expect(bodies.cleanupDuplicates).toBeUndefined();
  }
});
