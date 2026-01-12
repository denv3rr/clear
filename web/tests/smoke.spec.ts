import { expect, test } from "@playwright/test";

test("dashboard renders overview and OSINT callout", async ({ page }) => {
  await page.goto("/?demo=true");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByText("OSINT")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open OSINT" })).toBeVisible();
});

test("clients render with profiles", async ({ page }) => {
  await page.goto("/clients?demo=true");
  await expect(page.getByText("Portfolio Command Center")).toBeVisible();
  const clientButton = page.getByRole("button", { name: /Atlas Capital/i }).first();
  await expect(clientButton).toBeVisible();
  await clientButton.click();
  await expect(page.getByText("Client Profile")).toBeVisible();
  await expect(page.getByText("X: Sample Index")).toBeVisible();
});

test("trackers page renders live feed", async ({ page }) => {
  await page.goto("/osint?tab=trackers&demo=true");
  await expect(page.getByRole("heading", { name: "Live Trackers" })).toBeVisible();
  await expect(page.getByPlaceholder("Search flight number, operator, tail, ICAO24...")).toBeVisible();
});

test("intel and news render data", async ({ page }) => {
  await page.goto("/osint?tab=intel&demo=true");
  await expect(page.getByText("Global Impact Summary")).toBeVisible();
  await expect(page.getByText("Combined Overview")).toBeVisible();

  await page.goto("/osint?tab=news&demo=true");
  await expect(page.getByText("Market Signals")).toBeVisible();
  await expect(page.getByText("US Treasuries steady as auction demand improves")).toBeVisible();
});

test("osint tabs switch", async ({ page }) => {
  await page.goto("/osint?tab=trackers&demo=true");
  await expect(page.getByRole("heading", { name: "Live Trackers" })).toBeVisible();
  await page.getByRole("button", { name: "Intel" }).click();
  await expect(page.getByText("Global Impact Summary")).toBeVisible();
  await page.getByRole("button", { name: "News" }).click();
  await expect(page.getByText("Market Signals")).toBeVisible();
});

test("dashboard empty data states render", async ({ page }) => {
  await page.goto("/?demo=true&demo_empty=summary");
  await expect(page.getByText("No risk series available.")).toBeVisible();      
});

test("clients empty index renders", async ({ page }) => {
  await page.goto("/clients?demo=true&demo_empty=clients");
  await expect(page.getByText("No client profiles loaded.")).toBeVisible();
});

test("news empty feed renders", async ({ page }) => {
  await page.goto("/osint?tab=news&demo=true&demo_empty=news");
  await expect(page.getByText("No news items available.")).toBeVisible();
});
