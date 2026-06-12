// Centralized data-testid selectors for the FinAlly E2E suite.
//
// These match the actual testids exposed by the frontend (Task #4). Per-ticker
// elements use the pattern `<base>-<TICKER>`, e.g. watch-row-AAPL. Update this
// one file if the frontend changes its testids and every spec follows.

export const sel = {
  // Header
  header: "header",
  headerTotalValue: "total-value",
  headerCashBalance: "cash-balance",
  // connection-status carries data-status="connected|reconnecting|disconnected"
  connectionStatus: "connection-status",

  // Watchlist (watch-row-{TICKER} carries data-selected)
  watchlist: "watchlist",
  watchlistRow: (ticker: string) => `watch-row-${ticker}`,
  watchlistPrice: (ticker: string) => `watch-price-${ticker}`,
  watchlistRemove: (ticker: string) => `watch-remove-${ticker}`,
  addTickerInput: "watch-add-input",
  addTickerSubmit: "watch-add-btn",

  // Trade bar (falls back to selected ticker if trade-ticker is empty)
  tradeBar: "trade-bar",
  tradeTickerInput: "trade-ticker",
  tradeQtyInput: "trade-quantity",
  tradeBuy: "trade-buy",
  tradeSell: "trade-sell",
  tradeReset: "trade-reset",
  tradeStatus: "trade-status",

  // Positions table (clicking a row selects the ticker)
  positionsTable: "positions-table",
  positionRow: (ticker: string) => `position-row-${ticker}`,

  // Charts (canvas-based; assert on containers, not pixels)
  mainChart: "main-chart",
  mainChartCanvas: "main-chart-canvas",
  pnlChart: "pnl-chart",
  pnlChartCanvas: "pnl-chart-canvas",

  // Heatmap (SVG-based)
  heatmap: "heatmap",
  heatmapSvg: "heatmap-svg",
  heatTile: (ticker: string) => `heat-tile-${ticker}`,

  // Chat
  chatPanel: "chat-panel",
  chatHistory: "chat-history",
  chatInput: "chat-input",
  chatSend: "chat-send",
  chatLoading: "chat-loading",
  chatMsgUser: "chat-msg-user",
  chatMsgAssistant: "chat-msg-assistant",
  chatTradeChip: "chat-trade",
  chatWatchlistChip: "chat-watchlist",
} as const;

// Helper to build a Playwright testid locator string.
export const tid = (id: string) => `[data-testid="${id}"]`;
