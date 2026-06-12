"""Watchlist endpoint tests."""

from __future__ import annotations


async def test_list_watchlist_shape(client):
    resp = await client.get("/api/watchlist")
    assert resp.status_code == 200
    data = resp.json()
    # Seeded with the 10 default tickers.
    assert len(data) == 10
    aapl = next(row for row in data if row["ticker"] == "AAPL")
    assert set(aapl) == {"ticker", "price", "prev_price", "session_open", "change_pct"}
    assert aapl["price"] == 190.0
    assert aapl["session_open"] == 190.0
    assert aapl["change_pct"] == 0.0


async def test_change_pct_uses_session_open(client, app):
    # Move AAPL up from session_open 190 -> 199.5 (5%).
    app.state.cache.update("AAPL", 199.5)
    resp = await client.get("/api/watchlist")
    aapl = next(row for row in resp.json() if row["ticker"] == "AAPL")
    assert aapl["change_pct"] == 5.0
    assert aapl["prev_price"] == 190.0


async def test_add_ticker(client, app):
    resp = await client.post("/api/watchlist", json={"ticker": "pypl"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "ticker": "PYPL"}
    assert "PYPL" in app.state.source.added

    tickers = [row["ticker"] for row in (await client.get("/api/watchlist")).json()]
    assert "PYPL" in tickers


async def test_add_ticker_invalid(client):
    resp = await client.post("/api/watchlist", json={"ticker": "TOOLONGTICKER"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert "1-10" in body["error"]


async def test_remove_ticker(client, app):
    resp = await client.delete("/api/watchlist/AAPL")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "ticker": "AAPL"}
    assert "AAPL" in app.state.source.removed

    tickers = [row["ticker"] for row in (await client.get("/api/watchlist")).json()]
    assert "AAPL" not in tickers


async def test_remove_unknown_ticker(client):
    resp = await client.delete("/api/watchlist/ZZZZ")
    assert resp.status_code == 404
    assert resp.json()["ok"] is False
