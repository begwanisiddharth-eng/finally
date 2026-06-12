/** Helpers for component tests: seed and reset the global store. */

import { useStore } from "./store";
import type { Portfolio, WatchlistItem } from "./types";

/** The pristine store value (actions + initial data), captured at import time. */
const INITIAL = useStore.getState();

export function resetStore() {
  useStore.setState(
    {
      ...INITIAL,
      connection: "disconnected",
      prices: {},
      samples: {},
      watchlist: [],
      portfolio: null,
      history: [],
      selectedTicker: null,
      chat: [],
      chatLoading: false,
    },
    true,
  );
}

export const mockWatchlist: WatchlistItem[] = [
  { ticker: "AAPL", price: 195.5, prev_price: 194.2, session_open: 190.0, change_pct: 2.89 },
  { ticker: "TSLA", price: 245.1, prev_price: 248.0, session_open: 250.0, change_pct: -1.96 },
];

export const mockPortfolio: Portfolio = {
  cash_balance: 8500,
  total_value: 11234.56,
  positions: [
    {
      ticker: "AAPL",
      quantity: 10,
      avg_cost: 190,
      current_price: 195.5,
      market_value: 1955,
      unrealized_pnl: 55,
      pnl_pct: 2.89,
    },
    {
      ticker: "TSLA",
      quantity: 5,
      avg_cost: 250,
      current_price: 245.1,
      market_value: 1225.5,
      unrealized_pnl: -24.5,
      pnl_pct: -1.96,
    },
  ],
};
