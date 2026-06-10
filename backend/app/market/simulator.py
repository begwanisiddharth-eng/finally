1	"""GBM-based market simulator."""
2	
3	from __future__ import annotations
4	
5	import asyncio
6	import logging
7	import math
8	import random
9	
10	import numpy as np
11	
12	from .cache import PriceCache
13	from .interface import MarketDataSource
14	from .seed_prices import (
15	    CORRELATION_GROUPS,
16	    CROSS_GROUP_CORR,
17	    DEFAULT_PARAMS,
18	    INTRA_FINANCE_CORR,
19	    INTRA_TECH_CORR,
20	    SEED_PRICES,
21	    TICKER_PARAMS,
22	    TSLA_CORR,
23	)
24	
25	logger = logging.getLogger(__name__)
26	
27	
28	class GBMSimulator:
29	    """Geometric Brownian Motion simulator for correlated stock prices.
30	
31	    Math:
32	        S(t+dt) = S(t) * exp((mu - sigma^2/2) * dt + sigma * sqrt(dt) * Z)
33	
34	    Where:
35	        S(t)   = current price
36	        mu     = annualized drift (expected return)
37	        sigma  = annualized volatility
38	        dt     = time step as fraction of a trading year
39	        Z      = correlated standard normal random variable
40	
41	    The tiny dt (~8.5e-8 for 500ms ticks over 252 trading days * 6.5h/day)
42	    produces sub-cent moves per tick that accumulate naturally over time.
43	    """
44	
45	    # 500ms expressed as a fraction of a trading year
46	    # 252 trading days * 6.5 hours/day * 3600 seconds/hour = 5,896,800 seconds
47	    TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800
48	    DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR  # ~8.48e-8
49	
50	    def __init__(
51	        self,
52	        tickers: list[str],
53	        dt: float = DEFAULT_DT,
54	        event_probability: float = 0.001,
55	    ) -> None:
56	        self._dt = dt
57	        self._event_prob = event_probability
58	
59	        # Per-ticker state
60	        self._tickers: list[str] = []
61	        self._prices: dict[str, float] = {}
62	        self._params: dict[str, dict[str, float]] = {}
63	
64	        # Cholesky decomposition of the correlation matrix (for correlated moves)
65	        self._cholesky: np.ndarray | None = None
66	
67	        # Initialize all starting tickers
68	        for ticker in tickers:
69	            self._add_ticker_internal(ticker)
70	        self._rebuild_cholesky()
71	
72	    # --- Public API ---
73	
74	    def step(self) -> dict[str, float]:
75	        """Advance all tickers by one time step. Returns {ticker: new_price}.
76	
77	        This is the hot path — called every 500ms. Keep it fast.
78	        """
79	        n = len(self._tickers)
80	        if n == 0:
81	            return {}
82	
83	        # Generate n independent standard normal draws
84	        z_independent = np.random.standard_normal(n)
85	
86	        # Apply Cholesky to get correlated draws
87	        if self._cholesky is not None:
88	            z_correlated = self._cholesky @ z_independent
89	        else:
90	            z_correlated = z_independent
91	
92	        result: dict[str, float] = {}
93	        for i, ticker in enumerate(self._tickers):
94	            params = self._params[ticker]
95	            mu = params["mu"]
96	            sigma = params["sigma"]
97	
98	            # GBM: S(t+dt) = S(t) * exp((mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)
99	            drift = (mu - 0.5 * sigma**2) * self._dt
100	            diffusion = sigma * math.sqrt(self._dt) * z_correlated[i]
101	            self._prices[ticker] *= math.exp(drift + diffusion)
102	
103	            # Random event: ~0.1% chance per tick per ticker
104	            # With 10 tickers at 2 ticks/sec, expect an event ~every 50 seconds
105	            if random.random() < self._event_prob:
106	                shock_magnitude = random.uniform(0.02, 0.05)
107	                shock_sign = random.choice([-1, 1])
108	                self._prices[ticker] *= 1 + shock_magnitude * shock_sign
109	                logger.debug(
110	                    "Random event on %s: %.1f%% %s",
111	                    ticker,
112	                    shock_magnitude * 100,
113	                    "up" if shock_sign > 0 else "down",
114	                )
115	
116	            result[ticker] = round(self._prices[ticker], 2)
117	
118	        return result
119	
120	    def add_ticker(self, ticker: str) -> None:
121	        """Add a ticker to the simulation. Rebuilds the correlation matrix."""
122	        if ticker in self._prices:
123	            return
124	        self._add_ticker_internal(ticker)
125	        self._rebuild_cholesky()
126	
127	    def remove_ticker(self, ticker: str) -> None:
128	        """Remove a ticker from the simulation. Rebuilds the correlation matrix."""
129	        if ticker not in self._prices:
130	            return
131	        self._tickers.remove(ticker)
132	        del self._prices[ticker]
133	        del self._params[ticker]
134	        self._rebuild_cholesky()
135	
136	    def get_price(self, ticker: str) -> float | None:
137	        """Current price for a ticker, or None if not tracked."""
138	        return self._prices.get(ticker)
139	
140	    def get_tickers(self) -> list[str]:
141	        """Return the list of currently tracked tickers."""
142	        return list(self._tickers)
143	
144	    # --- Internals ---
145	
146	    def _add_ticker_internal(self, ticker: str) -> None:
147	        """Add a ticker without rebuilding Cholesky (for batch initialization)."""
148	        if ticker in self._prices:
149	            return
150	        self._tickers.append(ticker)
151	        self._prices[ticker] = SEED_PRICES.get(ticker, random.uniform(50.0, 300.0))
152	        self._params[ticker] = TICKER_PARAMS.get(ticker, dict(DEFAULT_PARAMS))
153	
154	    def _rebuild_cholesky(self) -> None:
155	        """Rebuild the Cholesky decomposition of the ticker correlation matrix.
156	
157	        Called whenever tickers are added or removed. O(n^2) but n < 50.
158	        """
159	        n = len(self._tickers)
160	        if n <= 1:
161	            self._cholesky = None
162	            return
163	
164	        # Build the correlation matrix
165	        corr = np.eye(n)
166	        for i in range(n):
167	            for j in range(i + 1, n):
168	                rho = self._pairwise_correlation(self._tickers[i], self._tickers[j])
169	                corr[i, j] = rho
170	                corr[j, i] = rho
171	
172	        self._cholesky = np.linalg.cholesky(corr)
173	
174	    @staticmethod
175	    def _pairwise_correlation(t1: str, t2: str) -> float:
176	        """Determine correlation between two tickers based on sector grouping.
177	
178	        Correlation structure:
179	          - Same tech sector:   0.6
180	          - Same finance sector: 0.5
181	          - TSLA with anything: 0.3 (it does its own thing)
182	          - Cross-sector:       0.3
183	          - Unknown tickers:    0.3
184	        """
185	        tech = CORRELATION_GROUPS["tech"]
186	        finance = CORRELATION_GROUPS["finance"]
187	
188	        # TSLA is in tech set but behaves independently
189	        if t1 == "TSLA" or t2 == "TSLA":
190	            return TSLA_CORR
191	
192	        if t1 in tech and t2 in tech:
193	            return INTRA_TECH_CORR
194	        if t1 in finance and t2 in finance:
195	            return INTRA_FINANCE_CORR
196	
197	        return CROSS_GROUP_CORR
198	
199	
200	class SimulatorDataSource(MarketDataSource):
201	    """MarketDataSource backed by the GBM simulator.
202	
203	    Runs a background asyncio task that calls GBMSimulator.step() every
204	    `update_interval` seconds and writes results to the PriceCache.
205	    """
206	
207	    def __init__(
208	        self,
209	        price_cache: PriceCache,
210	        update_interval: float = 0.5,
211	        event_probability: float = 0.001,
212	    ) -> None:
213	        self._cache = price_cache
214	        self._interval = update_interval
215	        self._event_prob = event_probability
216	        self._sim: GBMSimulator | None = None
217	        self._task: asyncio.Task | None = None
218	
219	    async def start(self, tickers: list[str]) -> None:
220	        self._sim = GBMSimulator(
221	            tickers=tickers,
222	            event_probability=self._event_prob,
223	        )
224	        # Seed the cache with initial prices so SSE has data immediately
225	        for ticker in tickers:
226	            price = self._sim.get_price(ticker)
227	            if price is not None:
228	                self._cache.update(ticker=ticker, price=price)
229	        self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")
230	        logger.info("Simulator started with %d tickers", len(tickers))
231	
232	    async def stop(self) -> None:
233	        if self._task and not self._task.done():
234	            self._task.cancel()
235	            try:
236	                await self._task
237	            except asyncio.CancelledError:
238	                pass
239	        self._task = None
240	        logger.info("Simulator stopped")
241	
242	    async def add_ticker(self, ticker: str) -> None:
243	        if self._sim:
244	            self._sim.add_ticker(ticker)
245	            # Seed cache immediately so the ticker has a price right away
246	            price = self._sim.get_price(ticker)
247	            if price is not None:
248	                self._cache.update(ticker=ticker, price=price)
249	            logger.info("Simulator: added ticker %s", ticker)
250	
251	    async def remove_ticker(self, ticker: str) -> None:
252	        if self._sim:
253	            self._sim.remove_ticker(ticker)
254	        self._cache.remove(ticker)
255	        logger.info("Simulator: removed ticker %s", ticker)
256	
257	    def get_tickers(self) -> list[str]:
258	        return self._sim.get_tickers() if self._sim else []
259	
260	    async def _run_loop(self) -> None:
261	        """Core loop: step the simulation, write to cache, sleep."""
262	        while True:
263	            try:
264	                if self._sim:
265	                    prices = self._sim.step()
266	                    for ticker, price in prices.items():
267	                        self._cache.update(ticker=ticker, price=price)
268	            except Exception:
269	                logger.exception("Simulator step failed")
270	            await asyncio.sleep(self._interval)
271	