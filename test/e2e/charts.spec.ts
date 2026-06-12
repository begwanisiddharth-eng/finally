import { test, expect } from "@playwright/test";
import { sel, tid } from "./selectors";

test.describe("heatmap and P&L chart render", () => {
  test.beforeEach(async ({ request }) => {
    await request.post("/api/portfolio/reset");
    // Two positions so the treemap has cells to lay out.
    await request.post("/api/portfolio/trade", {
      data: { ticker: "AAPL", quantity: 5, side: "buy" },
    });
    await request.post("/api/portfolio/trade", {
      data: { ticker: "MSFT", quantity: 3, side: "buy" },
    });
  });

  test("portfolio heatmap renders", async ({ page }) => {
    await page.goto("/");
    const heatmap = page.locator(tid(sel.heatmap));
    await expect(heatmap).toBeVisible();
    // The treemap renders as SVG with a tile per position.
    await expect(page.locator(tid(sel.heatmapSvg))).toBeVisible();
    await expect(page.locator(tid(sel.heatTile("AAPL")))).toBeVisible();
  });

  test("P&L chart renders", async ({ page }) => {
    await page.goto("/");
    const pnl = page.locator(tid(sel.pnlChart));
    await expect(pnl).toBeVisible();
    await expect(pnl.locator("canvas").first()).toBeVisible();
  });

  test("main chart area renders after selecting a ticker", async ({ page }) => {
    await page.goto("/");
    await page.locator(tid(sel.watchlistRow("AAPL"))).click();
    const chart = page.locator(tid(sel.mainChart));
    await expect(chart).toBeVisible();
    await expect(chart.locator("canvas").first()).toBeVisible();
  });

  test("history API returns portfolio snapshots", async ({ request }) => {
    const res = await request.get("/api/portfolio/history");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body)).toBeTruthy();
  });
});
