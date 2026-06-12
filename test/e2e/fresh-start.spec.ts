import { test, expect } from "@playwright/test";
import { sel, tid } from "./selectors";

const DEFAULT_TICKERS = [
  "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
  "NVDA", "META", "JPM", "V", "NFLX",
];

test.describe("fresh start", () => {
  test("watchlist API returns the 10 default tickers with prices", async ({ request }) => {
    const res = await request.get("/api/watchlist");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body)).toBeTruthy();
    const tickers = body.map((r: { ticker: string }) => r.ticker).sort();
    expect(tickers).toEqual([...DEFAULT_TICKERS].sort());
    for (const row of body) {
      expect(typeof row.price).toBe("number");
      expect(row.price).toBeGreaterThan(0);
      expect(row).toHaveProperty("prev_price");
      expect(row).toHaveProperty("session_open");
      expect(row).toHaveProperty("change_pct");
    }
  });

  test("portfolio API starts at $10,000 cash, no positions", async ({ request }) => {
    // A pristine portfolio equals the reset state ($10k, no positions); reset
    // first so this is deterministic across reruns on a persisted DB.
    await request.post("/api/portfolio/reset");
    const res = await request.get("/api/portfolio");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.cash_balance).toBeCloseTo(10000.0, 2);
    expect(body.positions).toEqual([]);
  });

  test("UI renders watchlist and chat panel on load", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(tid(sel.watchlist))).toBeVisible();
    await expect(page.locator(tid(sel.chatPanel))).toBeVisible();
    // The 10 default rows should render.
    for (const ticker of DEFAULT_TICKERS) {
      await expect(page.locator(tid(sel.watchlistRow(ticker)))).toBeVisible();
    }
  });

  test("prices stream and flash via SSE", async ({ page }) => {
    await page.goto("/");
    const priceCell = page.locator(tid(sel.watchlistPrice("AAPL")));
    await expect(priceCell).toBeVisible();
    const first = await priceCell.textContent();
    // Prices update on a ~500ms cadence; expect a change within a few seconds.
    await expect
      .poll(async () => priceCell.textContent(), { timeout: 8000, intervals: [500] })
      .not.toBe(first);
  });
});
