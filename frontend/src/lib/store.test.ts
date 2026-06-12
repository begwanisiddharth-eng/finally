import { useStore } from "./store";
import { resetStore } from "./testUtils";
import type { PriceEvent } from "./types";

beforeEach(() => resetStore());

const event = (over: Partial<PriceEvent> = {}): PriceEvent => ({
  ticker: "AAPL",
  price: 195.5,
  prev_price: 194.2,
  session_open: 190,
  change_pct: 2.89,
  direction: "up",
  timestamp: "2026-01-01T10:00:00Z",
  ...over,
});

describe("store.applyPriceEvent", () => {
  test("stores latest price and bumps the tick counter", () => {
    useStore.getState().applyPriceEvent(event());
    useStore.getState().applyPriceEvent(event({ price: 196 }));

    const live = useStore.getState().prices.AAPL;
    expect(live.price).toBe(196);
    expect(live.tick).toBe(2);
  });

  test("accumulates samples for sparklines", () => {
    useStore.getState().applyPriceEvent(event({ price: 195 }));
    useStore.getState().applyPriceEvent(event({ price: 196, timestamp: "2026-01-01T10:00:01Z" }));

    const samples = useStore.getState().samples.AAPL;
    expect(samples).toHaveLength(2);
    expect(samples[1].price).toBe(196);
  });

  test("auto-selects the first ticker seen", () => {
    expect(useStore.getState().selectedTicker).toBeNull();
    useStore.getState().applyPriceEvent(event({ ticker: "TSLA" }));
    expect(useStore.getState().selectedTicker).toBe("TSLA");
  });
});

describe("store connection + chat", () => {
  test("setConnection updates status", () => {
    useStore.getState().setConnection("connected");
    expect(useStore.getState().connection).toBe("connected");
  });

  test("addChatMessage appends in order", () => {
    useStore.getState().addChatMessage({ id: "1", role: "user", content: "hi" });
    useStore.getState().addChatMessage({ id: "2", role: "assistant", content: "hello" });
    const chat = useStore.getState().chat;
    expect(chat.map((m) => m.id)).toEqual(["1", "2"]);
  });
});
