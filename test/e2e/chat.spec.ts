import { test, expect } from "@playwright/test";
import { sel, tid } from "./selectors";

// Deterministic LLM_MOCK behavior (confirmed with llm-engineer):
// The mock parses the user message case-insensitively, emits structured
// intent, and the chat service runs it through the REAL trade/watchlist
// execution path, so state changes are genuine.
//   "buy <N> <TICKER>"   -> trades:[{ticker,side:"buy",quantity:N}]
//   "sell <N> <TICKER>"  -> trades:[{ticker,side:"sell",quantity:N}]
//   "watch|add <TICKER>" -> watchlist_changes:[{ticker,action:"add"}]
//   "unwatch|remove <T>" -> watchlist_changes:[{ticker,action:"remove"}]
// message strings:
//   trade:     "[MOCK] Executing: buy 10 AAPL."   (qty via %g, comma-joined)
//   watchlist: "[MOCK] Updating watchlist: add NVDA."
//   none:      "[MOCK] I am FinAlly running in mock mode. No actions taken."
const MOCK = {
  analyzePrompt: "tell me about my portfolio",
  analyzeMessage: "[MOCK] I am FinAlly running in mock mode. No actions taken.",
  buyPrompt: "buy 2 AAPL",
  buyMessage: "[MOCK] Executing: buy 2 AAPL.",
  buyTicker: "AAPL",
  buyQty: 2,
  watchPrompt: "watch PYPL",
  watchMessage: "[MOCK] Updating watchlist: add PYPL.",
  watchTicker: "PYPL",
};

test.describe("AI chat (mocked)", () => {
  test.beforeEach(async ({ request }) => {
    await request.post("/api/portfolio/reset");
  });

  test.afterEach(async ({ request }) => {
    await request.delete(`/api/watchlist/${MOCK.watchTicker}`);
  });

  test("chat API returns deterministic structured response for no-action prompt", async ({ request }) => {
    const res = await request.post("/api/chat", { data: { message: MOCK.analyzePrompt } });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.message).toBe(MOCK.analyzeMessage);
  });

  test("chat API buy returns the mock message and executes a real trade", async ({ request }) => {
    const res = await request.post("/api/chat", { data: { message: MOCK.buyPrompt } });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.message).toBe(MOCK.buyMessage);
    expect(body.trades).toContainEqual(
      expect.objectContaining({ ticker: MOCK.buyTicker, side: "buy", quantity: MOCK.buyQty }),
    );
    expect(body.trade_results?.[0]?.ok).toBe(true);

    // Real portfolio state reflects the buy.
    const portfolio = await (await request.get("/api/portfolio")).json();
    const pos = portfolio.positions.find((p: { ticker: string }) => p.ticker === MOCK.buyTicker);
    expect(pos?.quantity).toBeCloseTo(MOCK.buyQty, 3);
  });

  test("chat API watchlist add returns the mock message and updates the watchlist", async ({ request }) => {
    const res = await request.post("/api/chat", { data: { message: MOCK.watchPrompt } });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.message).toBe(MOCK.watchMessage);
    expect(body.watchlist_changes).toContainEqual(
      expect.objectContaining({ ticker: MOCK.watchTicker, action: "add" }),
    );

    const watchlist = await (await request.get("/api/watchlist")).json();
    expect(watchlist.map((r: { ticker: string }) => r.ticker)).toContain(MOCK.watchTicker);
  });

  test("chat buy beyond cash returns ok:false via the real execution path", async ({ request }) => {
    // Mock decides intent; real trade execution rejects insufficient cash.
    const res = await request.post("/api/chat", { data: { message: "buy 1000 AAPL" } });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.trade_results?.[0]?.ok).toBe(false);

    // No position should have been opened.
    const portfolio = await (await request.get("/api/portfolio")).json();
    expect(portfolio.positions.find((p: { ticker: string }) => p.ticker === "AAPL")).toBeFalsy();
  });

  test("chat UI sends a message and renders user + assistant messages", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(tid(sel.chatPanel))).toBeVisible();
    await page.locator(tid(sel.chatInput)).fill(MOCK.analyzePrompt);
    await page.locator(tid(sel.chatSend)).click();

    // One user bubble and one assistant bubble should render.
    await expect(page.locator(tid(sel.chatMsgUser))).toHaveCount(1, { timeout: 15_000 });
    const assistant = page.locator(tid(sel.chatMsgAssistant));
    await expect(assistant).toHaveCount(1, { timeout: 15_000 });
    await expect(assistant.last()).toContainText(MOCK.analyzeMessage);
  });

  test("chat-driven buy via the UI executes a trade", async ({ page, request }) => {
    await page.goto("/");
    await page.locator(tid(sel.chatInput)).fill(MOCK.buyPrompt);
    await page.locator(tid(sel.chatSend)).click();

    await expect(page.locator(tid(sel.chatMsgAssistant)).last()).toContainText(
      MOCK.buyMessage,
      { timeout: 15_000 },
    );

    await expect
      .poll(async () => {
        const body = await (await request.get("/api/portfolio")).json();
        const pos = body.positions.find(
          (p: { ticker: string }) => p.ticker === MOCK.buyTicker,
        );
        return pos ? pos.quantity : 0;
      }, { timeout: 15_000 })
      .toBeCloseTo(MOCK.buyQty, 3);
  });
});
