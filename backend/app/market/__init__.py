1	"""Market data subsystem for FinAlly.
2	
3	Public API:
4	    PriceUpdate         - Immutable price snapshot dataclass
5	    PriceCache          - Thread-safe in-memory price store
6	    MarketDataSource    - Abstract interface for data providers
7	    create_market_data_source - Factory that selects simulator or Massive
8	    create_stream_router - FastAPI router factory for SSE endpoint
9	"""
10	
11	from .cache import PriceCache
12	from .factory import create_market_data_source
13	from .interface import MarketDataSource
14	from .models import PriceUpdate
15	from .stream import create_stream_router
16	
17	__all__ = [
18	    "PriceUpdate",
19	    "PriceCache",
20	    "MarketDataSource",
21	    "create_market_data_source",
22	    "create_stream_router",
23	]
24	