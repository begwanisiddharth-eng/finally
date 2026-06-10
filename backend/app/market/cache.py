1	"""Thread-safe in-memory price cache."""
2	
3	from __future__ import annotations
4	
5	import time
6	from threading import Lock
7	
8	from .models import PriceUpdate
9	
10	
11	class PriceCache:
12	    """Thread-safe in-memory cache of the latest price for each ticker.
13	
14	    Writers: SimulatorDataSource or MassiveDataSource (one at a time).
15	    Readers: SSE streaming endpoint, portfolio valuation, trade execution.
16	    """
17	
18	    def __init__(self) -> None:
19	        self._prices: dict[str, PriceUpdate] = {}
20	        self._lock = Lock()
21	        self._version: int = 0  # Monotonically increasing; bumped on every update
22	
23	    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
24	        """Record a new price for a ticker. Returns the created PriceUpdate.
25	
26	        Automatically computes direction and change from the previous price.
27	        If this is the first update for the ticker, previous_price == price (direction='flat').
28	        """
29	        with self._lock:
30	            ts = timestamp or time.time()
31	            prev = self._prices.get(ticker)
32	            previous_price = prev.price if prev else price
33	
34	            update = PriceUpdate(
35	                ticker=ticker,
36	                price=round(price, 2),
37	                previous_price=round(previous_price, 2),
38	                timestamp=ts,
39	            )
40	            self._prices[ticker] = update
41	            self._version += 1
42	            return update
43	
44	    def get(self, ticker: str) -> PriceUpdate | None:
45	        """Get the latest price for a single ticker, or None if unknown."""
46	        with self._lock:
47	            return self._prices.get(ticker)
48	
49	    def get_all(self) -> dict[str, PriceUpdate]:
50	        """Snapshot of all current prices. Returns a shallow copy."""
51	        with self._lock:
52	            return dict(self._prices)
53	
54	    def get_price(self, ticker: str) -> float | None:
55	        """Convenience: get just the price float, or None."""
56	        update = self.get(ticker)
57	        return update.price if update else None
58	
59	    def remove(self, ticker: str) -> None:
60	        """Remove a ticker from the cache (e.g., when removed from watchlist)."""
61	        with self._lock:
62	            self._prices.pop(ticker, None)
63	
64	    @property
65	    def version(self) -> int:
66	        """Current version counter. Useful for SSE change detection."""
67	        return self._version
68	
69	    def __len__(self) -> int:
70	        with self._lock:
71	            return len(self._prices)
72	
73	    def __contains__(self, ticker: str) -> bool:
74	        with self._lock:
75	            return ticker in self._prices
76	