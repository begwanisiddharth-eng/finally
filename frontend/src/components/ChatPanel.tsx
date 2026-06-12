"use client";

/** AI chat panel: scrolling history, inline trade/watchlist confirmations, loading. */

import { useEffect, useRef, useState } from "react";
import { useStore } from "@/lib/store";
import { api } from "@/lib/api";
import { pct } from "@/lib/format";
import type { ChatMessage, ChatTrade, ChatWatchlistChange } from "@/lib/types";

let idCounter = 0;
const nextId = () => `m${++idCounter}`;

async function refreshAll() {
  const [portfolio, watchlist, history] = await Promise.allSettled([
    api.getPortfolio(),
    api.getWatchlist(),
    api.getHistory(),
  ]);
  if (portfolio.status === "fulfilled")
    useStore.setState({ portfolio: portfolio.value });
  if (watchlist.status === "fulfilled")
    useStore.setState({ watchlist: watchlist.value });
  if (history.status === "fulfilled")
    useStore.setState({ history: history.value });
}

function TradeChip({ trade }: { trade: ChatTrade }) {
  const ok = trade.ok !== false;
  return (
    <div
      data-testid="chat-trade"
      className={`flex items-center gap-2 rounded-md border px-2.5 py-1 text-xs ${
        ok ? "border-gain/40 bg-gain/10" : "border-loss/40 bg-loss/10"
      }`}
    >
      <span className={`font-semibold uppercase ${trade.side === "buy" ? "text-gain" : "text-loss"}`}>
        {trade.side}
      </span>
      <span className="tnum">
        {trade.quantity} {trade.ticker}
      </span>
      {trade.price != null && <span className="tnum text-muted">@ {trade.price.toFixed(2)}</span>}
      {!ok && <span className="text-loss">· {trade.error ?? "failed"}</span>}
    </div>
  );
}

function WatchChip({ change }: { change: ChatWatchlistChange }) {
  const ok = change.ok !== false;
  return (
    <div
      data-testid="chat-watchlist"
      className={`flex items-center gap-2 rounded-md border px-2.5 py-1 text-xs ${
        ok ? "border-accent-blue/40 bg-accent-blue/10" : "border-loss/40 bg-loss/10"
      }`}
    >
      <span className="font-semibold uppercase text-accent-blue">{change.action}</span>
      <span className="tnum">{change.ticker}</span>
      {!ok && <span className="text-loss">· {change.error ?? "failed"}</span>}
    </div>
  );
}

function Bubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div
      data-testid={`chat-msg-${message.role}`}
      className={`flex flex-col gap-1.5 ${isUser ? "items-end" : "items-start"}`}
    >
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
          isUser
            ? "bg-accent-blue/20 text-white"
            : "border border-border bg-bg-elevated/60 text-[#e6edf3]"
        }`}
      >
        {message.content}
      </div>
      {(message.trades?.length || message.watchlistChanges?.length) && (
        <div className="flex flex-wrap gap-1.5">
          {message.trades?.map((t, i) => <TradeChip key={`t${i}`} trade={t} />)}
          {message.watchlistChanges?.map((c, i) => <WatchChip key={`w${i}`} change={c} />)}
        </div>
      )}
    </div>
  );
}

export function ChatPanel() {
  const chat = useStore((s) => s.chat);
  const loading = useStore((s) => s.chatLoading);
  const addChatMessage = useStore((s) => s.addChatMessage);
  const setChatLoading = useStore((s) => s.setChatLoading);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [chat, loading]);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    addChatMessage({ id: nextId(), role: "user", content: text });
    setInput("");
    setChatLoading(true);

    try {
      const res = await api.chat(text);
      addChatMessage({
        id: nextId(),
        role: "assistant",
        content: res.message,
        trades: res.trade_results ?? res.trades,
        watchlistChanges: res.watchlist_results ?? res.watchlist_changes,
      });
      // The assistant may have traded or changed the watchlist; resync.
      await refreshAll();
    } catch (err) {
      addChatMessage({
        id: nextId(),
        role: "assistant",
        content: err instanceof Error ? `Error: ${err.message}` : "Something went wrong.",
      });
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <section className="panel flex min-h-0 flex-col" data-testid="chat-panel">
      <div className="border-b border-border px-4 py-2.5">
        <h2 className="panel-title">
          <span className="text-accent-yellow">●</span> AI Copilot
        </h2>
      </div>

      <div
        ref={scrollRef}
        className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3"
        data-testid="chat-history"
      >
        {chat.length === 0 && (
          <p className="m-auto max-w-[80%] text-center text-sm text-muted">
            Ask me about your portfolio, request analysis, or have me execute trades.
          </p>
        )}
        {chat.map((m) => (
          <Bubble key={m.id} message={m} />
        ))}
        {loading && (
          <div data-testid="chat-loading" className="flex items-center gap-1.5 px-1">
            <span className="h-2 w-2 animate-pulse-dot rounded-full bg-muted" />
            <span className="h-2 w-2 animate-pulse-dot rounded-full bg-muted [animation-delay:200ms]" />
            <span className="h-2 w-2 animate-pulse-dot rounded-full bg-muted [animation-delay:400ms]" />
          </div>
        )}
      </div>

      <form onSubmit={send} className="border-t border-border p-2.5">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Message FinAlly…"
            disabled={loading}
            data-testid="chat-input"
            className="min-w-0 flex-1 rounded-md border border-border bg-bg-base px-3 py-2 text-sm outline-none focus:border-accent-blue disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading}
            data-testid="chat-send"
            className="rounded-md bg-accent-purple px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-purple/80 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </form>
    </section>
  );
}
