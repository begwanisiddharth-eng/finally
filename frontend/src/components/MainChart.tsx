"use client";

/** Main chart: price history of the selected ticker, filled from SSE samples. */

import { useEffect, useRef } from "react";
import {
  AreaSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { useStore } from "@/lib/store";
import { price as fmtPrice, pct, pnlColor } from "@/lib/format";

const CHART_OPTIONS = {
  layout: {
    background: { color: "transparent" },
    textColor: "#7d8590",
    fontFamily: "var(--font-mono)",
  },
  grid: {
    vertLines: { color: "rgba(42, 42, 64, 0.4)" },
    horzLines: { color: "rgba(42, 42, 64, 0.4)" },
  },
  rightPriceScale: { borderColor: "#2a2a40" },
  timeScale: { borderColor: "#2a2a40", timeVisible: true, secondsVisible: false },
  crosshair: { mode: 1 as const },
  autoSize: true,
};

export function MainChart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  const selected = useStore((s) => s.selectedTicker);
  const samples = useStore((s) => (selected ? s.samples[selected] : undefined));
  const live = useStore((s) => (selected ? s.prices[selected] : undefined));

  // Create chart once.
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, CHART_OPTIONS);
    const series = chart.addSeries(AreaSeries, {
      lineColor: "#209dd7",
      topColor: "rgba(32, 157, 215, 0.30)",
      bottomColor: "rgba(32, 157, 215, 0.02)",
      lineWidth: 2,
      priceLineVisible: false,
    });
    chartRef.current = chart;
    seriesRef.current = series;
    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Push samples whenever they change. De-dupe by second so the series stays monotonic.
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    if (!samples || samples.length === 0) {
      series.setData([]);
      return;
    }
    const seen = new Set<number>();
    const data = [];
    for (const s of samples) {
      const t = Math.floor(s.time / 1000) as UTCTimestamp;
      if (seen.has(t)) {
        data[data.length - 1] = { time: t, value: s.price };
      } else {
        seen.add(t);
        data.push({ time: t, value: s.price });
      }
    }
    series.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [samples]);

  return (
    <section className="panel flex min-h-0 flex-col" data-testid="main-chart">
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div className="flex items-baseline gap-3">
          <h2 className="text-base font-bold">{selected ?? "—"}</h2>
          {live && (
            <>
              <span className="tnum text-sm">{fmtPrice(live.price)}</span>
              <span className={`tnum text-sm ${pnlColor(live.change_pct)}`}>
                {pct(live.change_pct)}
              </span>
            </>
          )}
        </div>
        <span className="panel-title">Session</span>
      </div>
      <div ref={containerRef} className="min-h-0 flex-1" data-testid="main-chart-canvas" />
    </section>
  );
}
