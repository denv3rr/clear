import { test, expect } from "@playwright/test";

const routes = [
  { path: "/", heading: "Tracker Command Center" },
  { path: "/trackers", heading: "Live Trackers" },
  { path: "/intel", heading: "Global Impact Summary" },
  { path: "/news", heading: "Market Signals" },
  { path: "/reports", heading: "Client Reporting" },
  { path: "/tools", heading: "Diagnostics" },
  { path: "/settings", heading: "System Settings Snapshot" }
];

test.describe("Clear Web smoke", () => {
  for (const route of routes) {
    test(`route ${route.path} renders`, async ({ page }) => {
      await page.goto(route.path);
      await expect(page.getByRole("heading", { name: route.heading })).toBeVisible();
    });
  }
});
