import { test, expect } from "@playwright/test";
import { sel, tid } from "./selectors";

test.describe("watchlist add/remove", () => {
  // Use a ticker that is not in the default seed set.
  const NEW_TICKER = "PYPL";

  test.afterEach(async ({ request }) => {
    // Clean up so reruns are deterministic; ignore failures.
    await request.delete(`/api/watchlist/${NEW_TICKER}`);
  });

  test("add a ticker via the UI", async ({ page }) => {
    await page.goto("/");
    await page.locator(tid(sel.addTickerInput)).fill(NEW_TICKER);
    await page.locator(tid(sel.addTickerSubmit)).click();
    await expect(page.locator(tid(sel.watchlistRow(NEW_TICKER)))).toBeVisible();
  });

  test("remove a ticker via the UI", async ({ page, request }) => {
    // Seed the ticker through the API so the test is independent.
    await request.post("/api/watchlist", { data: { ticker: NEW_TICKER } });
    await page.goto("/");
    await expect(page.locator(tid(sel.watchlistRow(NEW_TICKER)))).toBeVisible();
    await page.locator(tid(sel.watchlistRemove(NEW_TICKER))).click();
    await expect(page.locator(tid(sel.watchlistRow(NEW_TICKER)))).toHaveCount(0);
  });

  test("add ticker API validates and rejects bad input", async ({ request }) => {
    const res = await request.post("/api/watchlist", { data: { ticker: "toolongticker" } });
    expect(res.status()).toBe(400);
    const body = await res.json();
    expect(body.ok).toBe(false);
  });
});
