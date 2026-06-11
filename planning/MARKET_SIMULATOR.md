# Market Simulator Design

Approach and code structure for simulating realistic stock prices when no `MASSIVE_API_KEY`
is configured. The simulator is the default data source and requires no external dependencies
beyond `numpy`.

## Overview

The simulator uses **Geometric Brownian Motion (GBM)** — the standard model underlying
Black-Scholes option pricing. Prices evolve continuously with random noise, can never go
negative (multiplicative process), and exhibit the lognormal distribution seen in real markets.

Two layers:

| Class | Role |
|---|---|
| `GBMSimulator` | Pure math — maintains prices and advances them by one time step |
| `SimulatorDataSource` | asyncio adapter — wraps `GBMSimulator` in a background task, writes to `PriceCache` |

---

## GBM Math

At each time step a stock price evolves as:

```
S(t+dt) = S(t) * exp((mu - sigma²/2) * dt + sigma * sqrt(dt) * Z)
```

Where:
- `S(t)` — current price
- `mu` — annualized drift (expected return), e.g. `0.05` (5%)
- `sigma` — annualized volatility, e.g. `0.20` (20%)
- `dt` — time step as a fraction of a trading year
- `Z` — standard normal random variable drawn from N(0, 1)

The `exp()` form is the log-normal GBM solution. Key properties:
- Prices are **always positive** (`exp()` is always > 0)
- Returns are **lognormally distributed** (matches empirical market data)
- Variance grows as `sigma² * t` (variance scales with time)
- The `(mu - sigma²/2)` correction is the Itô correction for continuous-time processes

### Time Step

```python
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800

# For 500ms ticks:
dt = 0.5 / TRADING_SECONDS_PER_YEAR  # ≈ 8.48e-8
```

This tiny `dt` produces sub-cent moves per tick that accumulate naturally over time.
With `sigma=0.20` (MSFT), expected daily range:

```
daily_sigma = sigma * sqrt(1/252) ≈ 1.26%
```

Per 500ms tick: `1.26% / (6.5h * 7200 ticks/h) ≈ 0.000027%` — invisible individually,
realistic cumulatively.

---

## Correlated Moves

Real stocks don't move independently — tech names tend to move together in response to
macro news. The simulator models this with a **Cholesky decomposition** of a correlation
matrix.

### The Math

Given a correlation matrix `C` (symmetric, positive definite), compute its lower triangular
Cholesky factor `L` such that `C = L @ L.T`.

To generate n correlated standard normals from n independent draws:
```
Z_correlated = L @ Z_independent
```

The result has `Cov(Z_i, Z_j) = C[i,j]` by construction.

### Building the Correlation Matrix

```python
import numpy as np

def build_cholesky(tickers: list[str]) -> np.ndarray | None:
    n = len(tickers)
    if n <= 1:
        return None  # No correlation needed for a single ticker

    corr = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            rho = pairwise_correlation(tickers[i], tickers[j])
            corr[i, j] = rho
            corr[j, i] = rho

    return np.linalg.cholesky(corr)
```

### Correlation Groups

```python
CORRELATION_GROUPS = {
    "tech":    {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
}

INTRA_TECH_CORR    = 0.6   # Tech stocks move together
INTRA_FINANCE_CORR = 0.5   # Finance stocks move together
CROSS_GROUP_CORR   = 0.3   # Between sectors / unknown tickers
TSLA_CORR          = 0.3   # TSLA does its own thing (in tech group but treated as independent)

def pairwise_correlation(t1: str, t2: str) -> float:
    tech, finance = CORRELATION_GROUPS["tech"], CORRELATION_GROUPS["finance"]

    if t1 == "TSLA" or t2 == "TSLA":
        return TSLA_CORR
    if t1 in tech and t2 in tech:
        return INTRA_TECH_CORR
    if t1 in finance and t2 in finance:
        return INTRA_FINANCE_CORR
    return CROSS_GROUP_CORR
```

The correlation matrix must be **positive semi-definite** for Cholesky decomposition to
succeed. The above structure guarantees this for any combination of tickers because all
off-diagonal values are positive and below 1, producing a diagonally-dominant matrix.

---

## Random Events

Every step, each ticker has a small probability of a sudden shock move — a "news event":

```python
EVENT_PROBABILITY = 0.001  # 0.1% per tick per ticker

if random.random() < EVENT_PROBABILITY:
    shock_magnitude = random.uniform(0.02, 0.05)   # 2–5% move
    shock_sign = random.choice([-1, 1])
    price *= (1 + shock_magnitude * shock_sign)
```

With 10 tickers at 2 ticks/second: expected events ≈ `10 * 2 * 0.001 = 0.02/sec` →
roughly one event every 50 seconds somewhere on the watchlist. This keeps the UI visually
alive without making prices unrealistically jumpy.

---

## Seed Prices and Per-Ticker Parameters

```python
# backend/app/market/seed_prices.py

SEED_PRICES: dict[str, float] = {
    "AAPL":  190.00,
    "GOOGL": 175.00,
    "MSFT":  420.00,
    "AMZN":  185.00,
    "TSLA":  250.00,
    "NVDA":  800.00,
    "META":  500.00,
    "JPM":   195.00,
    "V":     280.00,
    "NFLX":  600.00,
}

# Per-ticker GBM parameters (sigma = annualized volatility, mu = annualized drift)
TICKER_PARAMS: dict[str, dict[str, float]] = {
    "AAPL":  {"sigma": 0.22, "mu": 0.05},
    "GOOGL": {"sigma": 0.25, "mu": 0.05},
    "MSFT":  {"sigma": 0.20, "mu": 0.05},
    "AMZN":  {"sigma": 0.28, "mu": 0.05},
    "TSLA":  {"sigma": 0.50, "mu": 0.03},   # High volatility, lower drift
    "NVDA":  {"sigma": 0.40, "mu": 0.08},   # High volatility, strong upward drift
    "META":  {"sigma": 0.30, "mu": 0.05},
    "JPM":   {"sigma": 0.18, "mu": 0.04},   # Low volatility (bank)
    "V":     {"sigma": 0.17, "mu": 0.04},   # Low volatility (payments)
    "NFLX":  {"sigma": 0.35, "mu": 0.05},
}

# Applied to any ticker not in the list above (dynamically added tickers)
DEFAULT_PARAMS: dict[str, float] = {"sigma": 0.25, "mu": 0.05}
```

Tickers added dynamically (not in `SEED_PRICES`) start at a random price in `[50, 300]`.

---

## GBMSimulator Implementation

```python
# backend/app/market/simulator.py

import math
import random
import numpy as np

from .seed_prices import (
    SEED_PRICES, TICKER_PARAMS, DEFAULT_PARAMS,
    CORRELATION_GROUPS, INTRA_TECH_CORR, INTRA_FINANCE_CORR,
    CROSS_GROUP_CORR, TSLA_CORR,
)


class GBMSimulator:
    """Geometric Brownian Motion simulator with correlated moves.

    Math: S(t+dt) = S(t) * exp((mu - sigma²/2)*dt + sigma*sqrt(dt)*Z)

    The dt is computed from the update interval and trading calendar:
        dt = interval_seconds / (252 * 6.5 * 3600)
    """

    TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800

    def __init__(
        self,
        tickers: list[str],
        dt: float = 0.5 / (252 * 6.5 * 3600),  # ≈ 8.48e-8 for 500ms ticks
        event_probability: float = 0.001,
    ) -> None:
        self._dt = dt
        self._event_prob = event_probability
        self._tickers: list[str] = []
        self._prices: dict[str, float] = {}
        self._params: dict[str, dict[str, float]] = {}
        self._cholesky: np.ndarray | None = None

        for ticker in tickers:
            self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def step(self) -> dict[str, float]:
        """Advance all tickers by one dt. Returns {ticker: new_price}.

        Hot path — called every 500ms. O(n) where n = number of tickers.
        """
        n = len(self._tickers)
        if n == 0:
            return {}

        # Generate correlated standard normals
        z_independent = np.random.standard_normal(n)
        z = self._cholesky @ z_independent if self._cholesky is not None else z_independent

        result: dict[str, float] = {}
        for i, ticker in enumerate(self._tickers):
            mu = self._params[ticker]["mu"]
            sigma = self._params[ticker]["sigma"]

            # GBM step: multiplicative log-normal move
            drift = (mu - 0.5 * sigma**2) * self._dt
            diffusion = sigma * math.sqrt(self._dt) * z[i]
            self._prices[ticker] *= math.exp(drift + diffusion)

            # Random event
            if random.random() < self._event_prob:
                shock = random.uniform(0.02, 0.05) * random.choice([-1, 1])
                self._prices[ticker] *= (1 + shock)

            result[ticker] = round(self._prices[ticker], 2)

        return result

    def add_ticker(self, ticker: str) -> None:
        """Add a ticker. Rebuilds the Cholesky matrix. O(n²), n < 50."""
        if ticker in self._prices:
            return
        self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker. Rebuilds the Cholesky matrix."""
        if ticker not in self._prices:
            return
        self._tickers.remove(ticker)
        del self._prices[ticker]
        del self._params[ticker]
        self._rebuild_cholesky()

    def get_price(self, ticker: str) -> float | None:
        return self._prices.get(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    def _add_ticker_internal(self, ticker: str) -> None:
        """Add without rebuilding Cholesky (used during batch initialization)."""
        self._tickers.append(ticker)
        self._prices[ticker] = SEED_PRICES.get(ticker, random.uniform(50.0, 300.0))
        self._params[ticker] = dict(TICKER_PARAMS.get(ticker, DEFAULT_PARAMS))

    def _rebuild_cholesky(self) -> None:
        n = len(self._tickers)
        if n <= 1:
            self._cholesky = None
            return

        corr = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                rho = self._pairwise_correlation(self._tickers[i], self._tickers[j])
                corr[i, j] = rho
                corr[j, i] = rho

        self._cholesky = np.linalg.cholesky(corr)

    @staticmethod
    def _pairwise_correlation(t1: str, t2: str) -> float:
        tech = CORRELATION_GROUPS["tech"]
        finance = CORRELATION_GROUPS["finance"]
        if t1 == "TSLA" or t2 == "TSLA":
            return TSLA_CORR
        if t1 in tech and t2 in tech:
            return INTRA_TECH_CORR
        if t1 in finance and t2 in finance:
            return INTRA_FINANCE_CORR
        return CROSS_GROUP_CORR
```

### Batch Initialization

During `__init__`, `_add_ticker_internal()` is called for each ticker (no Cholesky rebuild),
and `_rebuild_cholesky()` is called once at the end. This avoids O(n²) rebuilds for each
of the n tickers — the cost is O(n²) total, not O(n³).

### Dynamic Ticker Addition

When a ticker is added mid-session via `add_ticker()`:
- A seed price is assigned (from `SEED_PRICES` or random)
- The correlation matrix is expanded by one row/column and Cholesky is recomputed
- The new ticker will be included in the very next `step()` call

The Cholesky rebuild is O(n²). With n < 50 tickers this is negligible. At 50+ tickers,
a cached update (rank-1 Cholesky update) would be worth considering.

---

## SimulatorDataSource

```python
class SimulatorDataSource(MarketDataSource):
    """Wraps GBMSimulator in an asyncio background task.

    Calls sim.step() every `update_interval` seconds and writes to PriceCache.
    """

    def __init__(
        self,
        price_cache: PriceCache,
        update_interval: float = 0.5,
        event_probability: float = 0.001,
    ) -> None:
        self._cache = price_cache
        self._interval = update_interval
        self._event_prob = event_probability
        self._sim: GBMSimulator | None = None
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        dt = self._interval / GBMSimulator.TRADING_SECONDS_PER_YEAR
        self._sim = GBMSimulator(tickers=tickers, dt=dt, event_probability=self._event_prob)
        # Seed the cache immediately so SSE has data on first connect
        for ticker in tickers:
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)
        self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def add_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.add_ticker(ticker)
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)  # Seed immediately

    async def remove_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.remove_ticker(ticker)
        self._cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return self._sim.get_tickers() if self._sim else []

    async def _run_loop(self) -> None:
        while True:
            try:
                if self._sim:
                    prices = self._sim.step()
                    for ticker, price in prices.items():
                        self._cache.update(ticker=ticker, price=price)
            except Exception:
                logger.exception("Simulator step failed")
            await asyncio.sleep(self._interval)
```

Key points:
- `dt` is derived from the actual `update_interval`, keeping the GBM math consistent with
  the simulated clock rate
- The cache is **seeded immediately** in `start()` and in `add_ticker()` — no waiting for
  the first tick
- `asyncio.sleep` is called **after** the step, so the first update happens immediately
- Exceptions in `step()` are caught at the loop level to prevent the background task from
  silently dying

---

## Behavior Notes

| Property | Detail |
|---|---|
| Prices | Always positive (`exp()` is multiplicative) |
| Per-tick move | Sub-cent for default params; accumulates naturally over time |
| TSLA daily range | With `sigma=0.50`: ~3.15% expected daily range — matches reality |
| Random events | ~1 event/50s across a 10-ticker watchlist at default settings |
| Correlation matrix | Positive semi-definite by construction; Cholesky guaranteed to succeed |
| Cholesky rebuild | O(n²) on add/remove; negligible for n < 50 |
| Unknown tickers | Get `sigma=0.25, mu=0.05` and a random seed price in `[50, 300]` |
| Thread safety | `GBMSimulator` is not thread-safe; only the asyncio task should call `step()` |

### Calibrating Parameters

To calibrate `sigma` for a ticker:
```
sigma_daily = intraday_range / (price * 2.5)  # rough rule of thumb
sigma_annual = sigma_daily * sqrt(252)
```

For AAPL with typical $4 intraday range at $190: `sigma ≈ 4 / (190 * 2.5) * sqrt(252) ≈ 0.134`.
Using `0.22` gives a bit more visual drama while remaining in the realistic range.

---

## File Structure

```
backend/
  app/
    market/
      simulator.py    # GBMSimulator + SimulatorDataSource
      seed_prices.py  # SEED_PRICES, TICKER_PARAMS, DEFAULT_PARAMS, correlation constants
```

`seed_prices.py` is a pure constants module — no logic, no imports. `simulator.py` contains
both `GBMSimulator` (the math engine) and `SimulatorDataSource` (the async adapter). They
are in the same file because `SimulatorDataSource` is a thin wrapper with no value as a
standalone import.
