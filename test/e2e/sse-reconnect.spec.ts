import { test, expect } from "@playwright/test";
import { sel, tid } from "./selectors";

test.describe("SSE reconnection", () => {
  test("connection status shows connected on load", async ({ page }) => {
    await page.goto("/");
    const dot = page.locator(tid(sel.connectionStatus));
    await expect(dot).toBeVisible();
    // Connected state is signalled via data-status="connected".
    await expect(dot).toHaveAttribute("data-status", "connected", { timeout: 10_000 });
  });

  test("prices resume after the SSE stream is interrupted", async ({ page, context }) => {
    await page.goto("/");
    const priceCell = page.locator(tid(sel.watchlistPrice("AAPL")));
    await expect(priceCell).toBeVisible();

    // Confirm streaming is live.
    const before = await priceCell.textContent();
    await expect
      .poll(async () => priceCell.textContent(), { timeout: 8000 })
      .not.toBe(before);

    // Drop the SSE connection by aborting the stream request, then let the
    // browser's EventSource auto-reconnect (retry: 1000).
    await context.route("**/api/stream/prices", (route) => route.abort());
    await page.waitForTimeout(1500);
    await context.unroute("**/api/stream/prices");

    // After reconnect, prices should advance again.
    const afterDrop = await priceCell.textContent();
    await expect
      .poll(async () => priceCell.textContent(), { timeout: 12_000, intervals: [500] })
      .not.toBe(afterDrop);

    // Status indicator should be back to connected.
    await expect(page.locator(tid(sel.connectionStatus)))
      .toHaveAttribute("data-status", "connected", { timeout: 12_000 });
  });
});
