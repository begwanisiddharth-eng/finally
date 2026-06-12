"use client";

/** Top bar: brand, live total value, cash balance, connection status dot. */

import { useStore } from "@/lib/store";
import { money } from "@/lib/format";
import type { ConnectionStatus } from "@/lib/types";

const STATUS_META: Record<
  ConnectionStatus,
  { color: string; label: string; pulse: boolean }
> = {
  connected: { color: "#22c55e", label: "Live", pulse: false },
  reconnecting: { color: "#ecad0a", label: "Reconnecting", pulse: true },
  disconnected: { color: "#ef4444", label: "Offline", pulse: true },
};

export function Header() {
  const connection = useStore((s) => s.connection);
  const portfolio = useStore((s) => s.portfolio);
  const meta = STATUS_META[connection];

  return (
    <header
      className="flex items-center justify-between border-b border-border bg-bg-base/80 px-5 py-3 backdrop-blur"
      data-testid="header"
    >
      <div className="flex items-baseline gap-2">
        <span className="text-lg font-bold tracking-tight">
          Fin<span className="text-accent-yellow">Ally</span>
        </span>
        <span className="panel-title hidden sm:inline">AI Trading Workstation</span>
      </div>

      <div className="flex items-center gap-6">
        <div className="text-right">
          <div className="panel-title">Total Value</div>
          <div className="tnum text-xl font-semibold" data-testid="total-value">
            {portfolio ? money(portfolio.total_value) : "—"}
          </div>
        </div>
        <div className="text-right">
          <div className="panel-title">Cash</div>
          <div className="tnum text-xl font-semibold text-accent-blue" data-testid="cash-balance">
            {portfolio ? money(portfolio.cash_balance) : "—"}
          </div>
        </div>
        <div
          className="flex items-center gap-2 rounded-md border border-border px-3 py-1.5"
          data-testid="connection-status"
          data-status={connection}
        >
          <span
            className={`h-2.5 w-2.5 rounded-full ${meta.pulse ? "animate-pulse-dot" : ""}`}
            style={{ backgroundColor: meta.color, boxShadow: `0 0 8px ${meta.color}` }}
          />
          <span className="text-xs font-medium text-muted">{meta.label}</span>
        </div>
      </div>
    </header>
  );
}
