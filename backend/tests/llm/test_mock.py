"""Mock-mode determinism tests."""

from app.llm.mock import mock_response


def test_buy_trigger():
    r = mock_response("buy 10 AAPL")
    assert r.trades == [r.trades[0]]
    t = r.trades[0]
    assert (t.ticker, t.side, t.quantity) == ("AAPL", "buy", 10.0)
    assert r.watchlist_changes == []
    assert r.message == "[MOCK] Executing: buy 10 AAPL."


def test_sell_decimal_quantity():
    r = mock_response("please sell 2.5 tsla now")
    t = r.trades[0]
    assert (t.ticker, t.side, t.quantity) == ("TSLA", "sell", 2.5)
    assert r.message == "[MOCK] Executing: sell 2.5 TSLA."


def test_watch_add_trigger():
    r = mock_response("watch NVDA")
    assert r.trades == []
    w = r.watchlist_changes[0]
    assert (w.ticker, w.action) == ("NVDA", "add")
    assert r.message == "[MOCK] Updating watchlist: add NVDA."


def test_remove_trigger():
    r = mock_response("remove META")
    w = r.watchlist_changes[0]
    assert (w.ticker, w.action) == ("META", "remove")


def test_unwatch_trigger():
    r = mock_response("unwatch jpm")
    w = r.watchlist_changes[0]
    assert (w.ticker, w.action) == ("JPM", "remove")


def test_combined_trade_and_watchlist():
    r = mock_response("buy 10 AAPL and watch NVDA")
    assert len(r.trades) == 1
    assert len(r.watchlist_changes) == 1
    # Trade message takes precedence when both present.
    assert r.message == "[MOCK] Executing: buy 10 AAPL."


def test_no_trigger_plain_message():
    r = mock_response("how is my portfolio doing?")
    assert r.trades == []
    assert r.watchlist_changes == []
    assert r.message == "[MOCK] I am FinAlly running in mock mode. No actions taken."


def test_deterministic_repeat():
    msg = "buy 3 GOOGL"
    assert mock_response(msg).model_dump() == mock_response(msg).model_dump()
