1	"""Abstract interface for market data sources."""
2	
3	from __future__ import annotations
4	
5	from abc import ABC, abstractmethod
6	
7	
8	class MarketDataSource(ABC):
9	    """Contract for market data providers.
10	
11	    Implementations push price updates into a shared PriceCache on their own
12	    schedule. Downstream code never calls the data source directly for prices —
13	    it reads from the cache.
14	
15	    Lifecycle:
16	        source = create_market_data_source(cache)
17	        await source.start(["AAPL", "GOOGL", ...])
18	        # ... app runs ...
19	        await source.add_ticker("TSLA")
20	        await source.remove_ticker("GOOGL")
21	        # ... app shutting down ...
22	        await source.stop()
23	    """
24	
25	    @abstractmethod
26	    async def start(self, tickers: list[str]) -> None:
27	        """Begin producing price updates for the given tickers.
28	
29	        Starts a background task that periodically writes to the PriceCache.
30	        Must be called exactly once. Calling start() twice is undefined behavior.
31	        """
32	
33	    @abstractmethod
34	    async def stop(self) -> None:
35	        """Stop the background task and release resources.
36	
37	        Safe to call multiple times. After stop(), the source will not write
38	        to the cache again.
39	        """
40	
41	    @abstractmethod
42	    async def add_ticker(self, ticker: str) -> None:
43	        """Add a ticker to the active set. No-op if already present.
44	
45	        The next update cycle will include this ticker.
46	        """
47	
48	    @abstractmethod
49	    async def remove_ticker(self, ticker: str) -> None:
50	        """Remove a ticker from the active set. No-op if not present.
51	
52	        Also removes the ticker from the PriceCache.
53	        """
54	
55	    @abstractmethod
56	    def get_tickers(self) -> list[str]:
57	        """Return the current list of actively tracked tickers."""
58	