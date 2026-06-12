"use client";

/** Trade bar: ticker + quantity inputs, buy/sell, and portfolio reset. */

import { useState } from "react";
import { useStore } from "@/lib/store";
import { api } from "@/lib/api";
import type { TradeSide } from "@/lib/types";

async function refreshPortfolio() {
  const [portfolio, history] = await Promise.allSettled([
    api.getPortfolio(),
    api.getHistory(),
  ]);
  if (portfolio.status === "fulfilled")
    useStore.setState({ portfolio: portfolio.value });
  if (history.status === "fulfilled")
    useStore.setState({ history: history.value });
}

export function TradeBar() {
  const selected = useStore((s) => s.selectedTicker);
  const [ticker, setTicker] = useState("");
  const [quantity, setQuantity] = useState("");
  const [status, setStatus] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const effectiveTicker = (ticker.trim() || selected || "").toUpperCase();

  const submit = async (side: TradeSide) => {
    const qtyNum = Number(quantity);
    if (!effectiveTicker || !(qtyNum > 0)) {
      setStatus({ ok: false, text: "Enter a ticker and positive quantity" });
      return;
    }
    setBusy(true);
    setStatus(null);
    try {
      const res = await api.trade(effectiveTicker, qtyNum, side);
      setStatus({
        ok: true,
        text: `${side === "buy" ? "Bought" : "Sold"} ${res.quantity} ${res.ticker} @ ${res.price?.toFixed(2)}`,
      });
      setQuantity("");
      await refreshPortfolio();
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : "Trade failed" });
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    setBusy(true);
    try {
      await api.reset();
      setStatus({ ok: true, text: "Portfolio reset to $10,000" });
      await refreshPortfolio();
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : "Reset failed" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel px-4 py-3" data-testid="trade-bar">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="panel-title">Ticker</label>
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder={selected ?? "AAPL"}
            maxLength={10}
            data-testid="trade-ticker"
            className="tnum w-28 rounded-md border border-border bg-bg-base px-3 py-2 uppercase outline-none focus:border-accent-blue"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="panel-title">Quantity</label>
          <input
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder="0"
            inputMode="decimal"
            data-testid="trade-quantity"
            className="tnum w-28 rounded-md border border-border bg-bg-base px-3 py-2 outline-none focus:border-accent-blue"
          />
        </div>

        <button
          type="button"
          disabled={busy}
          onClick={() => submit("buy")}
          data-testid="trade-buy"
          className="rounded-md bg-gain/90 px-5 py-2 font-semibold text-white transition-colors hover:bg-gain disabled:opacity-50"
        >
          Buy
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => submit("sell")}
          data-testid="trade-sell"
          className="rounded-md bg-loss/90 px-5 py-2 font-semibold text-white transition-colors hover:bg-loss disabled:opacity-50"
        >
          Sell
        </button>

        <div className="ml-auto">
          <button
            type="button"
            disabled={busy}
            onClick={reset}
            data-testid="trade-reset"
            className="rounded-md border border-accent-purple bg-accent-purple/20 px-4 py-2 font-medium text-white transition-colors hover:bg-accent-purple/40 disabled:opacity-50"
          >
            Reset
          </button>
        </div>
      </div>

      {status && (
        <p
          data-testid="trade-status"
          className={`mt-2 text-sm ${status.ok ? "text-gain" : "text-loss"}`}
        >
          {status.text}
        </p>
      )}
    </section>
  );
}
