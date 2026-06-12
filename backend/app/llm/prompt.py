"""System prompt and prompt assembly for the FinAlly chat assistant."""

from __future__ import annotations

SYSTEM_PROMPT = (
    "You are FinAlly, an AI trading assistant inside a simulated trading "
    "workstation. The user trades a virtual portfolio with no real money.\n\n"
    "Your job:\n"
    "- Analyze the user's portfolio composition, risk, and profit/loss.\n"
    "- Suggest and execute trades when the user asks. Trades are market orders, "
    "filled instantly at the current price, with no fees.\n"
    "- Manage the watchlist proactively (add or remove tickers).\n"
    "- Be concise and data-driven. Reference the user's actual cash, positions, "
    "and live prices from the context below.\n\n"
    "When the user asks you to trade or change the watchlist, populate the "
    "`trades` and `watchlist_changes` fields. Use positive quantities (minimum "
    "0.001). Only include actions the user actually requested or clearly agreed "
    "to. If you are only answering a question, leave those lists empty. Always "
    "put your conversational reply in `message`."
)


def format_portfolio_context(
    cash_balance: float,
    total_value: float,
    positions: list[dict],
    watchlist: list[dict],
) -> str:
    """Render the live portfolio + watchlist into a compact text block.

    positions: dicts with ticker, quantity, avg_cost, current_price,
        unrealized_pnl, pnl_pct (the GET /api/portfolio position shape).
    watchlist: dicts with ticker, price, change_pct (the GET /api/watchlist shape).
    """
    lines = [
        "=== PORTFOLIO CONTEXT ===",
        f"Cash balance: ${cash_balance:,.2f}",
        f"Total portfolio value: ${total_value:,.2f}",
        "",
        "Positions:",
    ]
    if positions:
        for p in positions:
            lines.append(
                f"  {p['ticker']}: qty {p['quantity']:g} @ avg ${p['avg_cost']:,.2f}, "
                f"now ${p['current_price']:,.2f}, "
                f"P&L ${p['unrealized_pnl']:,.2f} ({p['pnl_pct']:+.2f}%)"
            )
    else:
        lines.append("  (none)")

    lines += ["", "Watchlist (live prices):"]
    if watchlist:
        for w in watchlist:
            price = w.get("price")
            price_str = f"${price:,.2f}" if price is not None else "n/a"
            change = w.get("change_pct")
            change_str = f"{change:+.2f}%" if change is not None else "n/a"
            lines.append(f"  {w['ticker']}: {price_str} ({change_str})")
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def build_messages(
    context: str,
    history: list[dict],
    user_message: str,
) -> list[dict]:
    """Assemble the chat messages list for the LLM call.

    history: prior chat_messages rows, each with 'role' and 'content',
        oldest first (already limited to the last 20 by the caller).
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": context},
    ]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})
    return messages
