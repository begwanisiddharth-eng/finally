1	"""SSE streaming endpoint for live price updates."""
2	
3	from __future__ import annotations
4	
5	import asyncio
6	import json
7	import logging
8	from collections.abc import AsyncGenerator
9	
10	from fastapi import APIRouter, Request
11	from fastapi.responses import StreamingResponse
12	
13	from .cache import PriceCache
14	
15	logger = logging.getLogger(__name__)
16	
17	router = APIRouter(prefix="/api/stream", tags=["streaming"])
18	
19	
20	def create_stream_router(price_cache: PriceCache) -> APIRouter:
21	    """Create the SSE streaming router with a reference to the price cache.
22	
23	    This factory pattern lets us inject the PriceCache without globals.
24	    """
25	
26	    @router.get("/prices")
27	    async def stream_prices(request: Request) -> StreamingResponse:
28	        """SSE endpoint for live price updates.
29	
30	        Streams all tracked ticker prices every ~500ms. The client connects
31	        with EventSource and receives events in the format:
32	
33	            data: {"AAPL": {"ticker": "AAPL", "price": 190.50, ...}, ...}
34	
35	        Includes a retry directive so the browser auto-reconnects on
36	        disconnection (EventSource built-in behavior).
37	        """
38	        return StreamingResponse(
39	            _generate_events(price_cache, request),
40	            media_type="text/event-stream",
41	            headers={
42	                "Cache-Control": "no-cache",
43	                "Connection": "keep-alive",
44	                "X-Accel-Buffering": "no",  # Disable nginx buffering if proxied
45	            },
46	        )
47	
48	    return router
49	
50	
51	async def _generate_events(
52	    price_cache: PriceCache,
53	    request: Request,
54	    interval: float = 0.5,
55	) -> AsyncGenerator[str, None]:
56	    """Async generator that yields SSE-formatted price events.
57	
58	    Sends all prices every `interval` seconds. Stops when the client
59	    disconnects (detected via request.is_disconnected()).
60	    """
61	    # Tell the client to retry after 1 second if the connection drops
62	    yield "retry: 1000\n\n"
63	
64	    last_version = -1
65	    client_ip = request.client.host if request.client else "unknown"
66	    logger.info("SSE client connected: %s", client_ip)
67	
68	    try:
69	        while True:
70	            # Check for client disconnect
71	            if await request.is_disconnected():
72	                logger.info("SSE client disconnected: %s", client_ip)
73	                break
74	
75	            current_version = price_cache.version
76	            if current_version != last_version:
77	                last_version = current_version
78	                prices = price_cache.get_all()
79	
80	                if prices:
81	                    data = {ticker: update.to_dict() for ticker, update in prices.items()}
82	                    payload = json.dumps(data)
83	                    yield f"data: {payload}\n\n"
84	
85	            await asyncio.sleep(interval)
86	    except asyncio.CancelledError:
87	        logger.info("SSE stream cancelled for: %s", client_ip)
88	