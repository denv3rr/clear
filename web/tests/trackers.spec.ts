import { expect, test } from "@playwright/test";

test("tracker map focus and filters respond", async ({ page }) => {
  await page.goto("/trackers?demo=true");
  await expect(page.getByRole("heading", { name: "Live Trackers" })).toBeVisible();
  await expect(page.getByText("Map Focus")).toBeVisible();

  const lockButton = page.getByRole("button", { name: /Lock View/i });
  await lockButton.click();
  await expect(page.getByText("View locked.")).toBeVisible();

  const followButton = page.getByRole("button", { name: /Follow/i });
  await expect(followButton).toBeDisabled();

  const flightsButton = page.getByRole("button", { name: /Flights/i }).first();
  await flightsButton.click();
  await expect(flightsButton).toContainText("Off");

  await expect(page.getByText("Operators", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /All Operators/i })).toBeVisible();

  const livePointsButton = page.getByRole("button", { name: /Live Points/i });
  await livePointsButton.click();
  await expect(livePointsButton).toContainText("Off");

  const historyButton = page.getByRole("button", { name: /History Line/i });
  await historyButton.click();
  await expect(historyButton).toContainText("Off");
});
