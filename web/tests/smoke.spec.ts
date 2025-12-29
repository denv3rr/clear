import { expect, test } from "@playwright/test";

test("dashboard renders tracker panels", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByText("Flight + Maritime Layer")).toBeVisible();
  await expect(page.getByText("Tracker Signals")).toBeVisible();
});

test("clients render with profiles", async ({ page }) => {
  await page.goto("/clients");
  await expect(page.getByText("Portfolio Command Center")).toBeVisible();
  const clientButton = page.getByRole("button", { name: /Atlas Capital/i }).first();
  await expect(clientButton).toBeVisible();
  await clientButton.click();
  await expect(page.getByText("Client Profile")).toBeVisible();
});

test("trackers page renders live feed", async ({ page }) => {
  await page.goto("/trackers");
  await expect(page.getByRole("heading", { name: "Live Trackers" })).toBeVisible();
  await expect(page.getByPlaceholder("Search flight number, operator, tail, ICAO24...")).toBeVisible();
});

test("intel and news render data", async ({ page }) => {
  await page.goto("/intel");
  await expect(page.getByText("Global Impact Summary")).toBeVisible();
  await expect(page.getByText("Combined Overview")).toBeVisible();

  await page.goto("/news");
  await expect(page.getByText("Market Signals")).toBeVisible();
  await expect(page.getByText("US Treasuries steady as auction demand improves")).toBeVisible();
});
