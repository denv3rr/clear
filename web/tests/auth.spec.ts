import { expect, test } from "@playwright/test";

test("shows auth error banner when API responds 401", async ({ page }) => {
  await page.route("**/api/health", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Invalid API key" })
    });
  });
  await page.route("**/api/clients", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Invalid API key" })
    });
  });

  await page.goto("/clients");
  await expect(page.getByText(/API health check failed/i)).toBeVisible();
  await expect(
    page.locator("p", { hasText: /authentication required/i }).first()
  ).toBeVisible();
});
