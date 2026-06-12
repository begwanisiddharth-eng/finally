import { test, expect } from "@playwright/test";
import { sel, tid } from "./selectors";

test.describe("buy and sell shares", () => {
  test.beforeEach(async ({ request }) => {
    // Start each test from a known clean portfolio.
    await request.post("/api/portfolio/reset");
  });

  test("buy shares via the trade bar updates positions and cash", async ({ page, request }) => {
    await page.goto("/");
    await page.locator(tid(sel.tradeTickerInput)).fill("AAPL");
    await page.locator(tid(sel.tradeQtyInput)).fill("5");
    await page.locator(tid(sel.tradeBuy)).click();

    // Position row should appear.
    await expect(page.locator(tid(sel.positionRow("AAPL")))).toBeVisible();

    // Verify backend state.
    const res = await request.get("/api/portfolio");
    const body = await res.json();
    const pos = body.positions.find((p: { ticker: string }) => p.ticker === "AAPL");
    expect(pos).toBeTruthy();
    expect(pos.quantity).toBeCloseTo(5, 3);
    expect(body.cash_balance).toBeLessThan(10000.0);
  });

  test("sell shares reduces the position", async ({ page, request }) => {
    // Buy first via API so the sell test is independent of the buy UI.
    await request.post("/api/portfolio/trade", {
      data: { ticker: "MSFT", quantity: 4, side: "buy" },
    });
    await page.goto("/");
    await expect(page.locator(tid(sel.positionRow("MSFT")))).toBeVisible();

    await page.locator(tid(sel.tradeTickerInput)).fill("MSFT");
    await page.locator(tid(sel.tradeQtyInput)).fill("4");
    await page.locator(tid(sel.tradeSell)).click();

    // Position fully closed.
    await expect(page.locator(tid(sel.positionRow("MSFT")))).toHaveCount(0);
    const res = await request.get("/api/portfolio");
    const body = await res.json();
    expect(body.positions.find((p: { ticker: string }) => p.ticker === "MSFT")).toBeFalsy();
  });

  test("trade API rejects insufficient cash", async ({ request }) => {
    const res = await request.post("/api/portfolio/trade", {
      data: { ticker: "AAPL", quantity: 1000000, side: "buy" },
    });
    expect(res.status()).toBe(400);
    const body = await res.json();
    expect(body.ok).toBe(false);
  });

  test("trade API rejects overselling", async ({ request }) => {
    const res = await request.post("/api/portfolio/trade", {
      data: { ticker: "TSLA", quantity: 10, side: "sell" },
    });
    expect(res.status()).toBe(400);
    const body = await res.json();
    expect(body.ok).toBe(false);
  });
});
