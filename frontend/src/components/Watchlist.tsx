"use client";

/** Watchlist panel: live price (flash), session change %, sparkline, add/remove. */

import { useState } from "react";
import { useStore } from "@/lib/store";
import { api } from "@/lib/api";
import { price as fmtPrice, pct, pnlColor } from "@/lib/format";
import { useFlash } from "@/lib/useFlash";
import { Sparkline } from "./Sparkline";

function Row({ ticker }: { ticker: string }) {
  const live = useStore((s) => s.prices[ticker]);
  const samples = useStore((s) => s.samples[ticker]) ?? [];
  const selected = useStore((s) => s.selectedTicker === ticker);
  const selectTicker = useStore((s) => s.selectTicker);
  const flash = useFlash(live?.price ?? 0);

  const changePct = live?.change_pct ?? 0;
  const up = changePct >= 0;

  const onRemove = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await api.removeTicker(ticker);
    useStore.setState((s) => ({
      watchlist: s.watchlist.filter((w) => w.ticker !== ticker),
    }));
  };

  const onSelectKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      selectTicker(ticker);
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => selectTicker(ticker)}
      onKeyDown={onSelectKey}
      data-testid={`watch-row-${ticker}`}
      data-selected={selected}
      className={`group grid w-full cursor-pointer grid-cols-[1fr_auto_auto] items-center gap-3 rounded-md px-3 py-2 text-left transition-colors ${
        selected ? "bg-bg-elevated ring-1 ring-accent-blue/40" : "hover:bg-bg-elevated/60"
      }`}
    >
      <div className="flex items-center gap-3">
        <span className="w-14 font-semibold">{ticker}</span>
        <Sparkline samples={samples} up={up} />
      </div>

      <div className={`tnum rounded px-1.5 text-right ${flash}`} data-testid={`watch-price-${ticker}`}>
        {live ? fmtPrice(live.price) : "—"}
      </div>

      <div className="flex items-center gap-2">
        <span className={`tnum w-16 text-right text-sm ${pnlColor(changePct)}`}>
          {live ? pct(changePct) : "—"}
        </span>
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Remove ${ticker}`}
          data-testid={`watch-remove-${ticker}`}
          className="flex h-5 w-5 items-center justify-center rounded text-muted opacity-0 transition-opacity hover:bg-loss/20 hover:text-loss group-hover:opacity-100"
        >
          ×
        </button>
      </div>
    </div>
  );
}

export function Watchlist() {
  const watchlist = useStore((s) => s.watchlist);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  const onAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const ticker = input.trim().toUpperCase();
    if (!ticker) return;
    setError(null);
    try {
      await api.addTicker(ticker);
      useStore.setState((s) => {
        if (s.watchlist.some((w) => w.ticker === ticker)) return s;
        const live = s.prices[ticker];
        return {
          watchlist: [
            ...s.watchlist,
            {
              ticker,
              price: live?.price ?? 0,
              prev_price: live?.prev_price ?? 0,
              session_open: live?.session_open ?? 0,
              change_pct: live?.change_pct ?? 0,
            },
          ],
        };
      });
      setInput("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add ticker");
    }
  };

  return (
    <section className="panel flex min-h-0 flex-col" data-testid="watchlist">
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <h2 className="panel-title">Watchlist</h2>
        <span className="tnum text-xs text-muted">{watchlist.length}</span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-1.5">
        {watchlist.map((w) => (
          <Row key={w.ticker} ticker={w.ticker} />
        ))}
      </div>

      <form onSubmit={onAdd} className="border-t border-border p-2">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Add ticker…"
            maxLength={10}
            data-testid="watch-add-input"
            className="tnum min-w-0 flex-1 rounded-md border border-border bg-bg-base px-2.5 py-1.5 text-sm uppercase outline-none focus:border-accent-blue"
          />
          <button
            type="submit"
            data-testid="watch-add-btn"
            className="rounded-md bg-accent-blue/90 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-blue"
          >
            Add
          </button>
        </div>
        {error && <p className="mt-1.5 text-xs text-loss">{error}</p>}
      </form>
    </section>
  );
}
