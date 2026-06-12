/** Same-origin REST client for the FinAlly backend (PLAN.md section 8). */

import type {
  ChatResponse,
  HistoryPoint,
  PersistedChatMessage,
  Portfolio,
  TradeResult,
  TradeSide,
  WatchlistItem,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  let data: unknown;
  try {
    data = await res.json();
  } catch {
    throw new Error(`Request failed: ${res.status} (non-JSON response)`);
  }
  const d = data as Record<string, unknown>;
  if (!res.ok || d?.ok === false) {
    throw new Error((d?.error as string) ?? `Request failed: ${res.status}`);
  }
  return data as T;
}

export const api = {
  getPortfolio: () => request<Portfolio>("/api/portfolio"),

  getHistory: () => request<HistoryPoint[]>("/api/portfolio/history"),

  getWatchlist: () => request<WatchlistItem[]>("/api/watchlist"),

  trade: (ticker: string, quantity: number, side: TradeSide) =>
    request<TradeResult>("/api/portfolio/trade", {
      method: "POST",
      body: JSON.stringify({ ticker, quantity, side }),
    }),

  reset: () =>
    request<{ ok: boolean }>("/api/portfolio/reset", { method: "POST" }),

  addTicker: (ticker: string) =>
    request<unknown>("/api/watchlist", {
      method: "POST",
      body: JSON.stringify({ ticker }),
    }),

  removeTicker: (ticker: string) =>
    request<unknown>(`/api/watchlist/${ticker}`, { method: "DELETE" }),

  chat: (message: string) =>
    request<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message }),
    }),

  getChatHistory: () => request<PersistedChatMessage[]>("/api/chat/history"),
};
