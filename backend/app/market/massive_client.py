1	"""Massive (Polygon.io) API client for real market data."""
2	
3	from __future__ import annotations
4	
5	import asyncio
6	import logging
7	
8	from massive import RESTClient
9	from massive.rest.models import SnapshotMarketType
10	
11	from .cache import PriceCache
12	from .interface import MarketDataSource
13	
14	logger = logging.getLogger(__name__)
15	
16	
17	class MassiveDataSource(MarketDataSource):
18	    """MarketDataSource backed by the Massive (Polygon.io) REST API.
19	
20	    Polls GET /v2/snapshot/locale/us/markets/stocks/tickers for all watched
21	    tickers in a single API call, then writes results to the PriceCache.
22	
23	    Rate limits:
24	      - Free tier: 5 req/min → poll every 15s (default)
25	      - Paid tiers: higher limits → poll every 2-5s
26	    """
27	
28	    def __init__(
29	        self,
30	        api_key: str,
31	        price_cache: PriceCache,
32	        poll_interval: float = 15.0,
33	    ) -> None:
34	        self._api_key = api_key
35	        self._cache = price_cache
36	        self._interval = poll_interval
37	        self._tickers: list[str] = []
38	        self._task: asyncio.Task | None = None
39	        self._client: RESTClient | None = None
40	
41	    async def start(self, tickers: list[str]) -> None:
42	        self._client = RESTClient(api_key=self._api_key)
43	        self._tickers = list(tickers)
44	
45	        # Do an immediate first poll so the cache has data right away
46	        await self._poll_once()
47	
48	        self._task = asyncio.create_task(self._poll_loop(), name="massive-poller")
49	        logger.info(
50	            "Massive poller started: %d tickers, %.1fs interval",
51	            len(tickers),
52	            self._interval,
53	        )
54	
55	    async def stop(self) -> None:
56	        if self._task and not self._task.done():
57	            self._task.cancel()
58	            try:
59	                await self._task
60	            except asyncio.CancelledError:
61	                pass
62	        self._task = None
63	        self._client = None
64	        logger.info("Massive poller stopped")
65	
66	    async def add_ticker(self, ticker: str) -> None:
67	        ticker = ticker.upper().strip()
68	        if ticker not in self._tickers:
69	            self._tickers.append(ticker)
70	            logger.info("Massive: added ticker %s (will appear on next poll)", ticker)
71	
72	    async def remove_ticker(self, ticker: str) -> None:
73	        ticker = ticker.upper().strip()
74	        self._tickers = [t for t in self._tickers if t != ticker]
75	        self._cache.remove(ticker)
76	        logger.info("Massive: removed ticker %s", ticker)
77	
78	    def get_tickers(self) -> list[str]:
79	        return list(self._tickers)
80	
81	    # --- Internal ---
82	
83	    async def _poll_loop(self) -> None:
84	        """Poll on interval. First poll already happened in start()."""
85	        while True:
86	            await asyncio.sleep(self._interval)
87	            await self._poll_once()
88	
89	    async def _poll_once(self) -> None:
90	        """Execute one poll cycle: fetch snapshots, update cache."""
91	        if not self._tickers or not self._client:
92	            return
93	
94	        try:
95	            # The Massive RESTClient is synchronous — run in a thread to
96	            # avoid blocking the event loop.
97	            snapshots = await asyncio.to_thread(self._fetch_snapshots)
98	            processed = 0
99	            for snap in snapshots:
100	                try:
101	                    price = snap.last_trade.price
102	                    # Massive timestamps are Unix milliseconds → convert to seconds
103	                    timestamp = snap.last_trade.timestamp / 1000.0
104	                    self._cache.update(
105	                        ticker=snap.ticker,
106	                        price=price,
107	                        timestamp=timestamp,
108	                    )
109	                    processed += 1
110	                except (AttributeError, TypeError) as e:
111	                    logger.warning(
112	                        "Skipping snapshot for %s: %s",
113	                        getattr(snap, "ticker", "???"),
114	                        e,
115	                    )
116	            logger.debug("Massive poll: updated %d/%d tickers", processed, len(self._tickers))
117	
118	        except Exception as e:
119	            logger.error("Massive poll failed: %s", e)
120	            # Don't re-raise — the loop will retry on the next interval.
121	            # Common failures: 401 (bad key), 429 (rate limit), network errors.
122	
123	    def _fetch_snapshots(self) -> list:
124	        """Synchronous call to the Massive REST API. Runs in a thread."""
125	        return self._client.get_snapshot_all(
126	            market_type=SnapshotMarketType.STOCKS,
127	            tickers=self._tickers,
128	        )
129	