"use client";

/** Portfolio value over time, from /api/portfolio/history snapshots. */

import { useEffect, useRef } from "react";
import {
  AreaSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { useStore } from "@/lib/store";

const CHART_OPTIONS = {
  layout: {
    background: { color: "transparent" },
    textColor: "#7d8590",
    fontFamily: "var(--font-mono)",
  },
  grid: {
    vertLines: { color: "rgba(42, 42, 64, 0.3)" },
    horzLines: { color: "rgba(42, 42, 64, 0.3)" },
  },
  rightPriceScale: { borderColor: "#2a2a40" },
  timeScale: { borderColor: "#2a2a40", timeVisible: true, secondsVisible: false },
  crosshair: { mode: 1 as const },
  autoSize: true,
};

export function PnlChart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const history = useStore((s) => s.history);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, CHART_OPTIONS);
    const series = chart.addSeries(AreaSeries, {
      lineColor: "#ecad0a",
      topColor: "rgba(236, 173, 10, 0.25)",
      bottomColor: "rgba(236, 173, 10, 0.02)",
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

  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    const seen = new Set<number>();
    const data = [];
    for (const point of history) {
      const t = Math.floor(Date.parse(point.recorded_at) / 1000) as UTCTimestamp;
      if (seen.has(t)) {
        data[data.length - 1] = { time: t, value: point.total_value };
      } else {
        seen.add(t);
        data.push({ time: t, value: point.total_value });
      }
    }
    series.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [history]);

  return (
    <section className="panel flex min-h-0 flex-col" data-testid="pnl-chart">
      <div className="border-b border-border px-4 py-2.5">
        <h2 className="panel-title">Portfolio Value</h2>
      </div>
      <div ref={containerRef} className="min-h-0 flex-1" data-testid="pnl-chart-canvas" />
    </section>
  );
}
