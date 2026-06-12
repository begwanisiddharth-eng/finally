import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          base: "#0d1117",
          panel: "#1a1a2e",
          elevated: "#21213a",
        },
        border: {
          DEFAULT: "#2a2a40",
          subtle: "#22222f",
        },
        accent: {
          yellow: "#ecad0a",
          blue: "#209dd7",
          purple: "#753991",
        },
        gain: "#22c55e",
        loss: "#ef4444",
        muted: "#7d8590",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      keyframes: {
        "flash-up": {
          "0%": { backgroundColor: "rgba(34, 197, 94, 0.35)" },
          "100%": { backgroundColor: "transparent" },
        },
        "flash-down": {
          "0%": { backgroundColor: "rgba(239, 68, 68, 0.35)" },
          "100%": { backgroundColor: "transparent" },
        },
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
      },
      animation: {
        "flash-up": "flash-up 500ms ease-out",
        "flash-down": "flash-down 500ms ease-out",
        "fade-in": "fade-in 200ms ease-out",
        "pulse-dot": "pulse-dot 1.5s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
