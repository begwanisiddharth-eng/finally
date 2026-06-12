"""Portfolio and trade endpoint tests."""

from __future__ import annotations


async def test_empty_portfolio(client):
    resp = await client.get("/api/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cash_balance"] == 10000.0
    assert data["total_value"] == 10000.0
    assert data["positions"] == []


async def test_buy_decrements_cash_and_creates_position(client):
    # Buy 10 AAPL @ 190 = 1900 cost.
    resp = await client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["price"] == 190.0
    assert body["cash_balance"] == 8100.0
    assert "executed_at" in body

    portfolio = (await client.get("/api/portfolio")).json()
    assert portfolio["cash_balance"] == 8100.0
    pos = portfolio["positions"][0]
    assert pos["ticker"] == "AAPL"
    assert pos["quantity"] == 10
    assert pos["avg_cost"] == 190.0
    assert pos["market_value"] == 1900.0
    assert pos["unrealized_pnl"] == 0.0


async def test_buy_recomputes_avg_cost(client, app):
    await client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10}
    )
    # Price moves to 210, buy 10 more -> avg = (1900 + 2100) / 20 = 200.
    app.state.cache.update("AAPL", 210.0)
    await client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10}
    )
    pos = (await client.get("/api/portfolio")).json()["positions"][0]
    assert pos["quantity"] == 20
    assert pos["avg_cost"] == 200.0
    # Current price 210, cost 200 -> pnl = 20 * 10 = 200, pct = 5%.
    assert pos["unrealized_pnl"] == 200.0
    assert pos["pnl_pct"] == 5.0


async def test_sell_reduces_position_and_adds_cash(client, app):
    await client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10}
    )
    app.state.cache.update("AAPL", 200.0)
    resp = await client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 4}
    )
    assert resp.status_code == 200
    # cash after buy = 8100, sell 4 @ 200 = +800 -> 8900.
    assert resp.json()["cash_balance"] == 8900.0

    pos = (await client.get("/api/portfolio")).json()["positions"][0]
    assert pos["quantity"] == 6
    assert pos["avg_cost"] == 190.0  # unchanged on sell


async def test_full_sell_removes_position(client):
    await client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 5}
    )
    await client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 5}
    )
    portfolio = (await client.get("/api/portfolio")).json()
    assert portfolio["positions"] == []
    assert portfolio["cash_balance"] == 10000.0


async def test_buy_insufficient_cash(client):
    # 100 MSFT @ 420 = 42000 > 10000.
    resp = await client.post(
        "/api/portfolio/trade", json={"ticker": "MSFT", "side": "buy", "quantity": 100}
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert "Insufficient cash" in body["error"]


async def test_oversell(client):
    await client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 5}
    )
    resp = await client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 10}
    )
    assert resp.status_code == 400
    assert "Insufficient shares" in resp.json()["error"]


async def test_trade_unknown_ticker(client):
    resp = await client.post(
        "/api/portfolio/trade", json={"ticker": "ZZZZ", "side": "buy", "quantity": 1}
    )
    assert resp.status_code == 400
    assert "No price" in resp.json()["error"]


async def test_history_and_reset(client):
    await client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10}
    )
    # Each trade writes a snapshot.
    history = (await client.get("/api/portfolio/history")).json()
    assert len(history) >= 1
    assert set(history[0]) == {"recorded_at", "total_value"}

    resp = await client.post("/api/portfolio/reset")
    assert resp.json() == {"ok": True}
    portfolio = (await client.get("/api/portfolio")).json()
    assert portfolio["cash_balance"] == 10000.0
    assert portfolio["positions"] == []
    assert (await client.get("/api/portfolio/history")).json() == []
