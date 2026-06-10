1	"""Factory for creating market data sources."""
2	
3	from __future__ import annotations
4	
5	import logging
6	import os
7	
8	from .cache import PriceCache
9	from .interface import MarketDataSource
10	from .massive_client import MassiveDataSource
11	from .simulator import SimulatorDataSource
12	
13	logger = logging.getLogger(__name__)
14	
15	
16	def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
17	    """Create the appropriate market data source based on environment variables.
18	
19	    - MASSIVE_API_KEY set and non-empty → MassiveDataSource (real market data)
20	    - Otherwise → SimulatorDataSource (GBM simulation)
21	
22	    Returns an unstarted source. Caller must await source.start(tickers).
23	    """
24	    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
25	
26	    if api_key:
27	        logger.info("Market data source: Massive API (real data)")
28	        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
29	    else:
30	        logger.info("Market data source: GBM Simulator")
31	        return SimulatorDataSource(price_cache=price_cache)
32	