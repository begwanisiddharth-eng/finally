"use client";

/** Positions table: ticker, qty, avg cost, current price, unrealized P&L, % change. */

import { useStore } from "@/lib/store";
import { money, price as fmtPrice, pct, qty, pnlColor } from "@/lib/format";

export function PositionsTable() {
  const portfolio = useStore((s) => s.portfolio);
  const selectTicker = useStore((s) => s.selectTicker);
  const positions = portfolio?.positions ?? [];

  return (
    <section className="panel flex min-h-0 flex-col" data-testid="positions-table">
      <div className="border-b border-border px-4 py-2.5">
        <h2 className="panel-title">Positions</h2>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-bg-panel">
            <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
              <th className="px-4 py-2 font-medium">Ticker</th>
              <th className="px-4 py-2 text-right font-medium">Qty</th>
              <th className="px-4 py-2 text-right font-medium">Avg Cost</th>
              <th className="px-4 py-2 text-right font-medium">Price</th>
              <th className="px-4 py-2 text-right font-medium">Mkt Value</th>
              <th className="px-4 py-2 text-right font-medium">Unrl P&L</th>
              <th className="px-4 py-2 text-right font-medium">%</th>
            </tr>
          </thead>
          <tbody>
            {positions.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-muted">
                  No open positions
                </td>
              </tr>
            ) : (
              positions.map((p) => (
                <tr
                  key={p.ticker}
                  onClick={() => selectTicker(p.ticker)}
                  data-testid={`position-row-${p.ticker}`}
                  className="cursor-pointer border-t border-border/60 hover:bg-bg-elevated/50"
                >
                  <td className="px-4 py-2 font-semibold">{p.ticker}</td>
                  <td className="tnum px-4 py-2 text-right">{qty(p.quantity)}</td>
                  <td className="tnum px-4 py-2 text-right">{fmtPrice(p.avg_cost)}</td>
                  <td className="tnum px-4 py-2 text-right">{fmtPrice(p.current_price)}</td>
                  <td className="tnum px-4 py-2 text-right">{money(p.market_value)}</td>
                  <td className={`tnum px-4 py-2 text-right ${pnlColor(p.unrealized_pnl)}`}>
                    {money(p.unrealized_pnl)}
                  </td>
                  <td className={`tnum px-4 py-2 text-right ${pnlColor(p.pnl_pct)}`}>
                    {pct(p.pnl_pct)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
