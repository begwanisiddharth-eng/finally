/** Global Zustand store: SSE prices, portfolio, watchlist, chat (PLAN.md section 10). */

import { create } from "zustand";
import type {
  ChatMessage,
  ConnectionStatus,
  Direction,
  HistoryPoint,
  Portfolio,
  PriceEvent,
  PriceSample,
  WatchlistItem,
} from "./types";

/** Latest live price snapshot for one ticker, kept in memory from the SSE stream. */
export interface LivePrice {
  price: number;
  prev_price: number;
  session_open: number;
  change_pct: number;
  direction: Direction;
  /** Bumped on every update so components can key off changes. */
  tick: number;
}

const MAX_SAMPLES = 600;

interface AppState {
  connection: ConnectionStatus;
  prices: Record<string, LivePrice>;
  /** In-memory price history per ticker for sparklines + main chart. */
  samples: Record<string, PriceSample[]>;
  watchlist: WatchlistItem[];
  portfolio: Portfolio | null;
  history: HistoryPoint[];
  selectedTicker: string | null;
  chat: ChatMessage[];
  chatLoading: boolean;

  setConnection: (status: ConnectionStatus) => void;
  applyPriceEvent: (event: PriceEvent) => void;
  setWatchlist: (items: WatchlistItem[]) => void;
  setPortfolio: (portfolio: Portfolio) => void;
  setHistory: (history: HistoryPoint[]) => void;
  selectTicker: (ticker: string) => void;
  addChatMessage: (message: ChatMessage) => void;
  setChat: (messages: ChatMessage[]) => void;
  setChatLoading: (loading: boolean) => void;
}

export const useStore = create<AppState>((set) => ({
  connection: "disconnected",
  prices: {},
  samples: {},
  watchlist: [],
  portfolio: null,
  history: [],
  selectedTicker: null,
  chat: [],
  chatLoading: false,

  setConnection: (connection) => set({ connection }),

  applyPriceEvent: (event) =>
    set((state) => {
      const prices = {
        ...state.prices,
        [event.ticker]: {
          price: event.price,
          prev_price: event.prev_price,
          session_open: event.session_open,
          change_pct: event.change_pct,
          direction: event.direction,
          tick: (state.prices[event.ticker]?.tick ?? 0) + 1,
        },
      };

      const prior = state.samples[event.ticker] ?? [];
      const next = [
        ...prior,
        { time: Date.parse(event.timestamp) || Date.now(), price: event.price },
      ];
      if (next.length > MAX_SAMPLES) next.shift();

      return {
        prices,
        samples: { ...state.samples, [event.ticker]: next },
        selectedTicker: state.selectedTicker ?? event.ticker,
      };
    }),

  setWatchlist: (watchlist) => set({ watchlist }),
  setPortfolio: (portfolio) => set({ portfolio }),
  setHistory: (history) => set({ history }),
  selectTicker: (selectedTicker) => set({ selectedTicker }),
  addChatMessage: (message) =>
    set((state) => ({ chat: [...state.chat, message] })),
  setChat: (chat) => set({ chat }),
  setChatLoading: (chatLoading) => set({ chatLoading }),
}));
