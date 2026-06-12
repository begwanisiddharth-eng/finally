import { test, expect } from "@playwright/test";
import { sel, tid } from "./selectors";

test.describe("portfolio reset", () => {
  test("reset restores $10k cash and clears positions", async ({ page, request }) => {
    // Establish a non-trivial position first.
    await request.post("/api/portfolio/trade", {
      data: { ticker: "AAPL", quantity: 3, side: "buy" },
    });

    await page.goto("/");
    await expect(page.locator(tid(sel.positionRow("AAPL")))).toBeVisible();

    await page.locator(tid(sel.tradeReset)).click();

    // Positions table empty for AAPL.
    await expect(page.locator(tid(sel.positionRow("AAPL")))).toHaveCount(0);

    const res = await request.get("/api/portfolio");
    const body = await res.json();
    expect(body.cash_balance).toBeCloseTo(10000.0, 2);
    expect(body.positions).toEqual([]);
  });

  test("reset API clears trades and snapshots", async ({ request }) => {
    await request.post("/api/portfolio/trade", {
      data: { ticker: "NVDA", quantity: 2, side: "buy" },
    });
    const res = await request.post("/api/portfolio/reset");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.ok).toBe(true);

    const portfolio = await (await request.get("/api/portfolio")).json();
    expect(portfolio.positions).toEqual([]);
    expect(portfolio.cash_balance).toBeCloseTo(10000.0, 2);
  });
});
