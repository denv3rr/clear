import { expect, test } from "@playwright/test";

test("system maintenance actions invoke API flows", async ({ page }) => {
  const bodies: Record<string, any> = {};
  await page.route("**/api/tools/diagnostics", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        duplicates: { accounts: { count: 2, clients: 1 } },
        orphans: { holdings: 1, lots: 2 },
        feeds: {
          summary: { total: 2, configured: 2, warnings: [], health_counts: { ok: 2 } },
          registry: { sources: [] }
        },
        trackers: { count: 12, warning_count: 0 },
        clients: { clients: 1, accounts: 2, holdings: 3, lots: 4 },
        reports: { items: 0, status: "ok" },
        system: { hostname: "local", os: "TestOS", cpu_usage: "0%", mem_usage: "0%" }
      })
    });
  });
  await page.route("**/api/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" })
    });
  });
  await page.route("**/api/maintenance/normalize-lots", async (route) => {
    bodies.normalize = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ normalized: true, message: "Normalization complete." })
    });
  });
  await page.route("**/api/maintenance/clear-report-cache", async (route) => {
    bodies.clearCache = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ cleared: true })
    });
  });
  await page.route("**/api/maintenance/cleanup-orphans", async (route) => {
    bodies.cleanupOrphans = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ removed_holdings: 1, removed_lots: 2 })
    });
  });
  await page.route("**/api/clients/duplicates/cleanup", async (route) => {
    bodies.cleanupDuplicates = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ removed: 2, remaining: { count: 0 } })
    });
  });

  page.on("dialog", async (dialog) => {
    await dialog.accept();
  });

  await page.goto("/system");
  await expect(page.getByText("System Settings & Diagnostics")).toBeVisible();

  await page.getByRole("button", { name: "Normalize Lot Timestamps" }).click();
  await expect(page.getByText("Normalization complete.")).toBeVisible();
  expect(bodies.normalize).toMatchObject({ confirm: true });

  await page.getByRole("button", { name: "Clear Report Cache" }).click();
  await expect(page.getByText("Report cache cleared.")).toBeVisible();
  expect(bodies.clearCache).toMatchObject({ confirm: true });

  await page.getByRole("button", { name: "Remove Orphaned Holdings/Lots" }).click();
  await expect(page.getByText("Removed 1 orphaned holdings and 2 orphaned lots.")).toBeVisible();
  expect(bodies.cleanupOrphans).toMatchObject({ confirm: true });

  await page.getByRole("button", { name: "Remove duplicates" }).click();
  await expect(page.getByText("Removed 2 duplicate accounts.")).toBeVisible();
  expect(bodies.cleanupDuplicates).toMatchObject({ confirm: true });
});
