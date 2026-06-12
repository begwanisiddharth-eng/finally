/** Shared types matching the backend API contract (PLAN.md section 8). */

export type Direction = "up" | "down" | "flat";

/** One SSE price event from /api/stream/prices. */
export interface PriceEvent {
  ticker: string;
  price: number;
  prev_price: number;
  session_open: number;
  change_pct: number;
  direction: Direction;
  timestamp: string;
}

/** A watchlist row from GET /api/watchlist. */
export interface WatchlistItem {
  ticker: string;
  price: number;
  prev_price: number;
  session_open: number;
  change_pct: number;
}

/** A position row from GET /api/portfolio. */
export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  pnl_pct: number;
}

/** GET /api/portfolio response. */
export interface Portfolio {
  cash_balance: number;
  total_value: number;
  positions: Position[];
}

/** One point in GET /api/portfolio/history. */
export interface HistoryPoint {
  recorded_at: string;
  total_value: number;
}

export type TradeSide = "buy" | "sell";

/** POST /api/portfolio/trade success response. */
export interface TradeResult {
  ok: boolean;
  ticker: string;
  side: TradeSide;
  quantity: number;
  price?: number;
  executed_at?: string;
  cash_balance?: number;
  error?: string;
}

/** A chat trade action proposed/executed by the assistant. */
export interface ChatTrade {
  ticker: string;
  side: TradeSide;
  quantity: number;
  price?: number;
  ok?: boolean;
  error?: string;
}

/** A chat watchlist action proposed/executed by the assistant. */
export interface ChatWatchlistChange {
  ticker: string;
  action: "add" | "remove";
  ok?: boolean;
  error?: string;
}

/** POST /api/chat response. */
export interface ChatResponse {
  message: string;
  trades?: ChatTrade[];
  watchlist_changes?: ChatWatchlistChange[];
  trade_results?: ChatTrade[];
  watchlist_results?: ChatWatchlistChange[];
}

/** A rendered chat message in the UI. */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  trades?: ChatTrade[];
  watchlistChanges?: ChatWatchlistChange[];
}

/** A persisted chat row from GET /api/chat/history. */
export interface PersistedChatMessage {
  role: "user" | "assistant";
  content: string;
  actions: {
    trades?: ChatTrade[];
    watchlist_changes?: ChatWatchlistChange[];
    trade_results?: ChatTrade[];
    watchlist_results?: ChatWatchlistChange[];
  } | null;
}

export type ConnectionStatus = "connected" | "reconnecting" | "disconnected";

/** One accumulated price sample for sparklines / charts (in-memory only). */
export interface PriceSample {
  time: number;
  price: number;
}
