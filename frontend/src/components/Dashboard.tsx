"use client";

/** Top-level workstation layout wiring all panels and the live data feed. */

import { useLiveData } from "@/lib/useLiveData";
import { Header } from "./Header";
import { Watchlist } from "./Watchlist";
import { MainChart } from "./MainChart";
import { Heatmap } from "./Heatmap";
import { PnlChart } from "./PnlChart";
import { PositionsTable } from "./PositionsTable";
import { TradeBar } from "./TradeBar";
import { ChatPanel } from "./ChatPanel";

export function Dashboard() {
  useLiveData();

  return (
    <div className="flex h-screen flex-col">
      <Header />

      <div className="grid min-h-0 flex-1 grid-cols-[260px_1fr_340px] gap-3 p-3">
        {/* Left rail: watchlist. */}
        <Watchlist />

        {/* Center: charts, trade bar, positions. */}
        <div className="grid min-h-0 grid-rows-[1.4fr_auto_1fr] gap-3">
          <div className="grid min-h-0 grid-cols-2 gap-3">
            <MainChart />
            <div className="grid min-h-0 grid-rows-2 gap-3">
              <Heatmap />
              <PnlChart />
            </div>
          </div>
          <TradeBar />
          <PositionsTable />
        </div>

        {/* Right rail: AI chat. */}
        <ChatPanel />
      </div>
    </div>
  );
}
