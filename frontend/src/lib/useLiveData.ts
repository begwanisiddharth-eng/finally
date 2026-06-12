"use client";

/** Wires the SSE price stream and periodic REST refresh into the store. */

import { useEffect } from "react";
import { api } from "./api";
import { useStore } from "./store";
import type { ChatMessage, PersistedChatMessage, PriceEvent } from "./types";

/** How often to re-pull portfolio/watchlist/history from REST. */
const REFRESH_MS = 5000;

/** Map a persisted chat row to the UI message shape (executed results win). */
function toChatMessage(row: PersistedChatMessage, i: number): ChatMessage {
  return {
    id: `h${i}`,
    role: row.role,
    content: row.content,
    trades: row.actions?.trade_results ?? row.actions?.trades,
    watchlistChanges: row.actions?.watchlist_results ?? row.actions?.watchlist_changes,
  };
}

export function useLiveData() {
  const setConnection = useStore((s) => s.setConnection);
  const applyPriceEvent = useStore((s) => s.applyPriceEvent);
  const setWatchlist = useStore((s) => s.setWatchlist);
  const setPortfolio = useStore((s) => s.setPortfolio);
  const setHistory = useStore((s) => s.setHistory);
  const setChat = useStore((s) => s.setChat);

  // SSE price stream.
  useEffect(() => {
    const source = new EventSource("/api/stream/prices");

    source.onopen = () => setConnection("connected");

    source.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data) as PriceEvent;
        applyPriceEvent(event);
      } catch {
        console.warn("Malformed SSE event; skipping:", e.data);
      }
    };

    // EventSource auto-reconnects (server sends retry: 1000); reflect that here.
    source.onerror = () => {
      setConnection(
        source.readyState === EventSource.CONNECTING
          ? "reconnecting"
          : "disconnected",
      );
    };

    return () => source.close();
  }, [setConnection, applyPriceEvent]);

  // Periodic REST refresh of portfolio state.
  useEffect(() => {
    let cancelled = false;

    const pull = async () => {
      const [portfolio, watchlist, history] = await Promise.allSettled([
        api.getPortfolio(),
        api.getWatchlist(),
        api.getHistory(),
      ]);
      if (cancelled) return;
      if (portfolio.status === "fulfilled") setPortfolio(portfolio.value);
      if (watchlist.status === "fulfilled") setWatchlist(watchlist.value);
      if (history.status === "fulfilled") setHistory(history.value);
    };

    pull();
    const id = setInterval(pull, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [setPortfolio, setWatchlist, setHistory]);

  // Rehydrate persisted chat history once on load (the backend keeps the
  // conversation the model sees; this keeps the UI in sync after a refresh).
  useEffect(() => {
    let cancelled = false;
    api.getChatHistory().then(
      (rows) => {
        // Only apply if the user hasn't started a conversation in the
        // meantime, so a slow history fetch can't clobber a sent message.
        if (!cancelled && rows.length && useStore.getState().chat.length === 0) {
          setChat(rows.map(toChatMessage));
        }
      },
      () => {},
    );
    return () => {
      cancelled = true;
    };
  }, [setChat]);
}
