"use client";

/** Tiny canvas sparkline drawn from in-memory SSE samples. */

import { useEffect, useRef } from "react";
import type { PriceSample } from "@/lib/types";

interface Props {
  samples: PriceSample[];
  up: boolean;
  width?: number;
  height?: number;
}

export function Sparkline({ samples, up, width = 72, height = 24 }: Props) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    if (samples.length < 2) return;

    const values = samples.map((s) => s.price);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const stepX = width / (values.length - 1);
    const pad = 2;

    const y = (v: number) =>
      height - pad - ((v - min) / span) * (height - pad * 2);

    const color = up ? "#22c55e" : "#ef4444";

    ctx.beginPath();
    values.forEach((v, i) => {
      const px = i * stepX;
      const py = y(v);
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = "round";
    ctx.stroke();

    // Soft fill under the line.
    ctx.lineTo(width, height);
    ctx.lineTo(0, height);
    ctx.closePath();
    ctx.fillStyle = `${color}1a`;
    ctx.fill();
  }, [samples, up, width, height]);

  return <canvas ref={ref} style={{ width, height }} aria-hidden />;
}
