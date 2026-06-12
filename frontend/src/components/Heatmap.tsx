"use client";

/** Portfolio heatmap: treemap of positions, sized by weight, colored by P&L. */

import { useMemo } from "react";
import { useStore } from "@/lib/store";
import { pct } from "@/lib/format";
import type { Position } from "@/lib/types";

interface Tile {
  pos: Position;
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Squarified-ish treemap: greedily slice the longest axis by remaining weight. */
function layout(positions: Position[], width: number, height: number): Tile[] {
  const total = positions.reduce((sum, p) => sum + Math.abs(p.market_value), 0);
  if (total === 0) return [];

  const sorted = [...positions].sort(
    (a, b) => Math.abs(b.market_value) - Math.abs(a.market_value),
  );

  const tiles: Tile[] = [];
  let x = 0;
  let y = 0;
  let w = width;
  let h = height;
  let remaining = total;

  sorted.forEach((pos, i) => {
    const frac = Math.abs(pos.market_value) / remaining;
    if (i === sorted.length - 1) {
      tiles.push({ pos, x, y, w, h });
      return;
    }
    if (w >= h) {
      const tileW = w * frac;
      tiles.push({ pos, x, y, w: tileW, h });
      x += tileW;
      w -= tileW;
    } else {
      const tileH = h * frac;
      tiles.push({ pos, x, y, w, h: tileH });
      y += tileH;
      h -= tileH;
    }
    remaining -= Math.abs(pos.market_value);
  });

  return tiles;
}

/** Map a P&L percent to a green/red background, intensity scaled to magnitude. */
function tileColor(pnlPct: number): string {
  const magnitude = Math.min(Math.abs(pnlPct) / 10, 1);
  const alpha = 0.15 + magnitude * 0.55;
  return pnlPct >= 0
    ? `rgba(34, 197, 94, ${alpha})`
    : `rgba(239, 68, 68, ${alpha})`;
}

export function Heatmap() {
  const portfolio = useStore((s) => s.portfolio);
  const positions = portfolio?.positions ?? [];

  // Use a 100x100 viewBox and let SVG scale to the container.
  const tiles = useMemo(() => layout(positions, 100, 100), [positions]);

  return (
    <section className="panel flex min-h-0 flex-col" data-testid="heatmap">
      <div className="border-b border-border px-4 py-2.5">
        <h2 className="panel-title">Positions Heatmap</h2>
      </div>
      <div className="min-h-0 flex-1 p-2">
        {tiles.length === 0 ? (
          <div className="grid h-full place-items-center text-sm text-muted">
            No positions yet
          </div>
        ) : (
          <svg
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            className="h-full w-full"
            data-testid="heatmap-svg"
          >
            {tiles.map(({ pos, x, y, w, h }) => (
              <g key={pos.ticker} data-testid={`heat-tile-${pos.ticker}`}>
                <rect
                  x={x}
                  y={y}
                  width={w}
                  height={h}
                  fill={tileColor(pos.pnl_pct)}
                  stroke="#0d1117"
                  strokeWidth={0.6}
                />
                {w > 12 && h > 10 && (
                  <text
                    x={x + w / 2}
                    y={y + h / 2}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill="#e6edf3"
                    style={{ fontSize: Math.min(w, h) * 0.18, fontWeight: 700 }}
                  >
                    <tspan x={x + w / 2} dy="-0.3em">
                      {pos.ticker}
                    </tspan>
                    <tspan
                      x={x + w / 2}
                      dy="1.3em"
                      style={{ fontSize: Math.min(w, h) * 0.13, fontWeight: 500 }}
                    >
                      {pct(pos.pnl_pct)}
                    </tspan>
                  </text>
                )}
              </g>
            ))}
          </svg>
        )}
      </div>
    </section>
  );
}
