"use client";

/** Returns a CSS animation class that flashes green/red when value changes, then clears. */

import { useEffect, useRef, useState } from "react";
import type { Direction } from "./types";

const FLASH_MS = 500;

export function useFlash(value: number): string {
  const prev = useRef<number | null>(null);
  const [flash, setFlash] = useState<Direction | null>(null);

  useEffect(() => {
    if (prev.current !== null && value !== prev.current) {
      setFlash(value > prev.current ? "up" : "down");
      const id = setTimeout(() => setFlash(null), FLASH_MS);
      prev.current = value;
      return () => clearTimeout(id);
    }
    prev.current = value;
  }, [value]);

  if (flash === "up") return "animate-flash-up";
  if (flash === "down") return "animate-flash-down";
  return "";
}
