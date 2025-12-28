import { test, expect } from "@playwright/test";

const routes = [
  { path: "/", heading: "Tracker Signals" },
  { path: "/trackers", heading: "Live Trackers" },
  { path: "/intel", heading: "Global Impact Summary" },
  { path: "/news", heading: "Market Signals" },
  { path: "/reports", heading: "Client Reporting" },
  { path: "/tools", heading: "Diagnostics" },
  { path: "/settings", heading: "System Settings Snapshot" }
];

test.describe("Clear Web smoke", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/health", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" })
      });
    });
  });

  for (const route of routes) {
    test(`route ${route.path} renders`, async ({ page }) => {
      await page.goto(route.path);
      await expect(page.getByRole("heading", { name: route.heading })).toBeVisible();
    });
  }

  test("clients page shows auth failure banner", async ({ page }) => {
    await page.route("**/api/clients**", async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid API key" })
      });
    });
    await page.goto("/clients");
    await expect(page.getByText("Client index failed", { exact: false })).toBeVisible();
  });

  test("clients page surfaces network failures", async ({ page }) => {
    await page.route("**/api/clients**", async (route) => {
      await route.abort();
    });
    await page.goto("/clients");
    await expect(page.getByText("API unreachable", { exact: false })).toBeVisible();
  });

  test("settings stores api key for authenticated clients fetch", async ({ page }) => {
    await page.route("**/api/settings", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          settings: { credentials: {} },
          feeds: {},
          system: {},
          system_metrics: {}
        })
      });
    });
    await page.route("**/api/clients**", async (route) => {
      const headers = route.request().headers();
      const apiKey = headers["x-api-key"];
      if (apiKey !== "test-key") {
        await route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Invalid API key" })
        });
        return;
      }
      const url = new URL(route.request().url());
      const path = url.pathname;
      if (path === "/api/clients") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            clients: [
              {
                client_id: "c1",
                name: "Test Client",
                accounts_count: 0,
                holdings_count: 0
              }
            ]
          })
        });
        return;
      }
      if (path === "/api/clients/c1") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            client_id: "c1",
            name: "Test Client",
            accounts_count: 0,
            holdings_count: 0,
            tax_profile: {},
            accounts: []
          })
        });
        return;
      }
      if (path.endsWith("/dashboard")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            client: {
              client_id: "c1",
              name: "Test Client",
              accounts_count: 0,
              holdings_count: 0
            },
            interval: "1M",
            totals: {
              total_value: 0,
              market_value: 0,
              manual_value: 0,
              holdings_count: 0
            },
            holdings: [],
            manual_holdings: [],
            history: [],
            risk: {},
            regime: {},
            diagnostics: { sectors: [], gainers: [], losers: [], hhi: 0 },
            warnings: []
          })
        });
        return;
      }
      if (path.endsWith("/patterns")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            entropy: 0.1,
            wave_surface: { z: [[0]] },
            fft_surface: { z: [[0]] }
          })
        });
        return;
      }
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not found" })
      });
    });

    await page.goto("/settings");
    await page.getByPlaceholder("Paste API key").fill("test-key");
    await page.getByRole("button", { name: "Save Key" }).click();
    await page.goto("/clients");
    const clientButton = page
      .getByRole("button", { name: /Test Client/i })
      .first();
    await expect(clientButton).toBeVisible();
  });

  test("news page uses stored api key for feeds", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("clear_api_key", "test-key");
    });
    await page.route("**/api/intel/meta**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          regions: [{ name: "Global", industries: ["all"] }],
          industries: ["all"],
          categories: [],
          sources: ["SourceA"]
        })
      });
    });
    await page.route("**/api/intel/news**", async (route) => {
      const headers = route.request().headers();
      if (headers["x-api-key"] !== "test-key") {
        await route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Invalid API key" })
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [{ title: "Market Signal Alpha", source: "SourceA" }],
          cached: false,
          stale: false,
          skipped: []
        })
      });
    });
    await page.goto("/news");
    await expect(page.getByText("Market Signal Alpha")).toBeVisible();
  });

  test("news page renders empty-state messaging", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("clear_api_key", "test-key");
    });
    await page.route("**/api/intel/meta**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          regions: [{ name: "Global", industries: ["all"] }],
          industries: ["all"],
          categories: [],
          sources: []
        })
      });
    });
    await page.route("**/api/intel/news**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [],
          cached: false,
          stale: false,
          skipped: []
        })
      });
    });
    await page.goto("/news");
    await expect(page.getByText("No news items available.")).toBeVisible();
  });

  test("clients page renders empty-state messaging", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("clear_api_key", "test-key");
    });
    await page.route("**/api/clients**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ clients: [] })
      });
    });
    await page.goto("/clients");
    await expect(page.getByText("No client profiles loaded.")).toBeVisible();
  });

  test("trackers page uses stored api key for snapshot", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("clear_api_key", "test-key");
    });
    await page.route("**/api/trackers/snapshot**", async (route) => {
      const headers = route.request().headers();
      if (headers["x-api-key"] !== "test-key") {
        await route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Invalid API key" })
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          count: 1,
          warnings: [],
          points: [
            {
              id: "t1",
              kind: "flight",
              label: "TEST123",
              category: "military",
              lat: 40.0,
              lon: -70.0
            }
          ]
        })
      });
    });
    await page.route("**/ws/trackers**", async (route) => {
      await route.abort();
    });
    await page.goto("/trackers");
    await expect(page.getByText("TEST123")).toBeVisible();
  });

  test("dashboard renders risk, map, and live feed with snapshot data", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("clear_api_key", "test-key");
    });
    await page.route("**/api/intel/summary**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ risk_level: "Moderate", risk_score: 4.2 })
      });
    });
    await page.route("**/api/trackers/snapshot**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          count: 1,
          warnings: [],
          points: [
            {
              id: "t1",
              kind: "flight",
              label: "TEST123",
              category: "military",
              lat: 40.0,
              lon: -70.0
            }
          ]
        })
      });
    });
    await page.route("**/ws/trackers**", async (route) => {
      await route.abort();
    });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Global Patterns" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Flight + Maritime Layer" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Tracker Signals" })).toBeVisible();
    await expect(page.getByText("TEST123")).toBeVisible();
  });

  test("dashboard surfaces empty tracker snapshots", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("clear_api_key", "test-key");
    });
    await page.route("**/api/intel/summary**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ risk_level: "Moderate", risk_score: 4.2 })
      });
    });
    await page.route("**/api/trackers/snapshot**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          count: 0,
          warnings: ["No live flight data returned from the flight feed."],
          points: []
        })
      });
    });
    await page.route("**/ws/trackers**", async (route) => {
      await route.abort();
    });
    await page.goto("/");
    await expect(page.getByText("No tracker points in snapshot.")).toBeVisible();
    await expect(page.getByText("No live tracker data available.")).toBeVisible();
  });

  test("reports page renders markdown output", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("clear_api_key", "test-key");
    });
    await page.route("**/api/clients**", async (route) => {
      const url = new URL(route.request().url());
      if (url.pathname === "/api/clients") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            clients: [
              {
                client_id: "c1",
                name: "Test Client",
                accounts_count: 0,
                holdings_count: 0
              }
            ]
          })
        });
        return;
      }
      if (url.pathname === "/api/clients/c1") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            client_id: "c1",
            name: "Test Client",
            accounts_count: 0,
            holdings_count: 0,
            accounts: []
          })
        });
        return;
      }
      await route.fallback();
    });
    await page.route("**/api/reports/client/c1**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          content: "# Executive Summary\n\n- Alpha\n- Beta\n",
          format: "md"
        })
      });
    });
    await page.goto("/reports");
    await page.getByRole("button", { name: /Test Client/i }).click();
    await page.getByRole("button", { name: "Generate Report" }).click();
    await expect(page.getByRole("heading", { name: "Executive Summary" })).toBeVisible();
  });
});
