import { expect, test } from "@playwright/test";

test.describe("globe fail-safe visual regression", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("tracker globe unavailable state matches snapshot", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.route("**/api/osint/scene/trackers**", async (route) => {
      await route.abort();
    });
    await page.route("**/api/trackers/snapshot**", async (route) => {
      await route.abort();
    });
    await page.goto("/osint?tab=trackers");
    await page.getByTestId("osint-open-globe").click();
    await expect(page.getByTestId("globe-overlay")).toBeVisible();
    await expect(page.getByTestId("globe-overlay").getByText("Unavailable", { exact: true })).toBeVisible();
    await expect(
      page.getByTestId("globe-overlay").getByText(
        "The immersive scene could not be recovered. Retry or close the overlay."
      )
    ).toBeVisible();
    await expect(page.getByTestId("globe-overlay")).toHaveScreenshot(
      "tracker-globe-overview.png",
      {
        animations: "disabled",
        caret: "hide",
        maxDiffPixels: 20,
        scale: "css"
      }
    );
  });

  test("intel globe unavailable state matches snapshot", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.route("**/api/osint/scene/intel**", async (route) => {
      await route.abort();
    });
    await page.goto("/osint?tab=intel");
    await page.getByTestId("osint-open-globe").click();
    await expect(page.getByTestId("globe-overlay")).toBeVisible();
    await expect(page.getByTestId("globe-overlay").getByText("Unavailable", { exact: true })).toBeVisible();
    await expect(
      page.getByTestId("globe-overlay").getByText(
        "The immersive scene could not be recovered. Retry or close the overlay."
      )
    ).toBeVisible();
    await expect(page.getByTestId("globe-overlay")).toHaveScreenshot(
      "intel-globe-conflict-focus.png",
      {
        animations: "disabled",
        caret: "hide",
        maxDiffPixels: 20,
        scale: "css"
      }
    );
  });
});
