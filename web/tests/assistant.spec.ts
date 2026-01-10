import { expect, test, type Page } from "@playwright/test";

async function stubSystemRoutes(page: Page) {
  await page.route("**/api/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" })
    });
  });
  await page.route("**/api/tools/diagnostics", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        duplicates: { accounts: { count: 0, clients: 0 } },
        orphans: { holdings: 0, lots: 0 },
        feeds: {
          summary: { total: 0, configured: 0, warnings: [], health_counts: { ok: 0 } },
          registry: { sources: [] }
        },
        trackers: { count: 0, warning_count: 0 },
        clients: { clients: 0, accounts: 0, holdings: 0, lots: 0 },
        reports: { items: 0, status: "ok" },
        intel: { news_cache: { status: "ok", items: 0, age_hours: 0 } },
        system: { hostname: "local", os: "TestOS", cpu_usage: "0%", mem_usage: "0%" }
      })
    });
  });
}

async function stubAppRoutes(page: Page) {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.startsWith("/api/assistant/")) {
      return route.fallback();
    }
    if (url.pathname === "/api/clients") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ clients: [], meta: {} })
      });
    }
    if (url.pathname.startsWith("/api/clients/")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ client: null, meta: {} })
      });
    }
    if (url.pathname === "/api/trackers/snapshot") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], count: 0, bounds: null, meta: {} })
      });
    }
    if (url.pathname === "/api/trackers/filters") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ operators: [], categories: [], countries: [] })
      });
    }
    if (url.pathname === "/api/intel/summary") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ summary: [], meta: {} })
      });
    }
    if (url.pathname === "/api/intel/meta") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ regions: [], industries: [], sources: [] })
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ meta: {} })
    });
  });
}

async function openAssistant(page: Page) {
  const assistantVisible = page.locator("button:visible", {
    hasText: "Assistant"
  });
  const toggle = page.getByRole("button", { name: "Toggle navigation" });
  if ((await assistantVisible.count()) === 0 && (await toggle.count())) {
    await toggle.first().click();
  }
  await expect(assistantVisible.first()).toBeVisible();
  await assistantVisible.first().click();
  await expect(page.getByRole("heading", { name: "AI Assistant" })).toBeVisible();
}

async function navigateViaNav(page: Page, label: string) {
  const link = page.getByRole("link", { name: label });
  if ((await link.count()) > 0) {
    await link.first().click();
    return;
  }
  const toggle = page.getByRole("button", { name: "Toggle navigation" });
  if (await toggle.count()) {
    await toggle.first().click();
  }
  await page.getByRole("link", { name: label }).first().click();
}

test("assistant sends context and renders response", async ({ page }) => {
  await stubSystemRoutes(page);
  await stubAppRoutes(page);
  await page.addInitScript(() => {
    localStorage.setItem("clear_api_key", "test-key");
  });

  let requestBody: Record<string, unknown> | null = null;
  let requestHeaders: Record<string, string> | null = null;
  await page.route("**/api/assistant/query", async (route) => {
    const request = route.request();
    requestBody = request.postDataJSON() as Record<string, unknown>;
    requestHeaders = request.headers();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        answer: "Assistant response ready.",
        confidence: "medium",
        sources: [{ route: "/api/intel/summary", source: "intel" }],
        warnings: ["Demo response"],
        routing: { rule: "news", handler: "handle_news" }
      })
    });
  });

  await page.goto("/system");
  await openAssistant(page);

  await page.getByText("Region").locator("..").locator("input").fill("EMEA");
  await page.getByText("Industry").locator("..").locator("input").fill("Energy");
  await page.getByPlaceholder("AAPL, MSFT").fill("AAPL, MSFT");
  await page.getByPlaceholder("bbc.com, cnbc.com").fill("bbc.com, cnbc.com");
  await page.getByText("Client ID").locator("..").locator("input").fill("c1");
  await page.getByText("Account ID").locator("..").locator("input").fill("a1");

  const questionInput = page.getByPlaceholder("Ask a question...");
  await questionInput.fill("What changed?");
  await questionInput.press("Enter");

  await expect(page.getByText("What changed?")).toBeVisible();
  await expect(page.getByText("Assistant response ready.")).toBeVisible();
  await expect(page.getByText("Confidence: medium")).toBeVisible();
  await expect(page.getByText("Routing: news (handle_news)")).toBeVisible();
  await expect(page.getByText("Sources: /api/intel/summary")).toBeVisible();
  await expect(page.getByText("Warnings: Demo response")).toBeVisible();

  expect(requestHeaders?.["x-api-key"]).toBe("test-key");
  expect(requestBody?.question).toBe("What changed?");
  expect(requestBody?.context).toMatchObject({
    region: "EMEA",
    industry: "Energy",
    tickers: ["AAPL", "MSFT"],
    client_id: "c1",
    account_id: "a1"
  });
  expect(requestBody?.sources).toEqual(["bbc.com", "cnbc.com"]);
});

test("assistant context scope persists across pages", async ({ page }) => {
  await stubSystemRoutes(page);
  await stubAppRoutes(page);
  await page.addInitScript(() => {
    localStorage.setItem("clear_api_key", "test-key");
  });
  await page.goto("/");
  await page.evaluate(() => {
    localStorage.setItem(
      "clear.assistant.context",
      JSON.stringify({ clientId: "client-1", accountId: "acct-1" })
    );
  });

  await page.goto("/clients");
  await expect
    .poll(() =>
      page.evaluate(() => window.localStorage.getItem("clear.assistant.context"))
    )
    .toContain("client-1");

  await page.goto("/trackers");
  await expect
    .poll(() =>
      page.evaluate(() => window.localStorage.getItem("clear.assistant.context"))
    )
    .toContain("acct-1");
});

test("assistant surfaces auth failures", async ({ page }) => {
  await stubSystemRoutes(page);
  await page.route("**/api/assistant/query", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Unauthorized" })
    });
  });

  await page.goto("/system");
  await openAssistant(page);

  const questionInput = page.getByPlaceholder("Ask a question...");
  await questionInput.fill("Status?");
  await questionInput.press("Enter");

  await expect(
    page.getByText("Error: Could not connect to the AI assistant.")
  ).toBeVisible();
});
