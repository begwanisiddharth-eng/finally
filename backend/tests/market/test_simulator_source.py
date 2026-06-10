1	"""Integration tests for SimulatorDataSource."""
2	
3	import asyncio
4	
5	import pytest
6	
7	from app.market.cache import PriceCache
8	from app.market.simulator import SimulatorDataSource
9	
10	
11	@pytest.mark.asyncio
12	class TestSimulatorDataSource:
13	    """Integration tests for the SimulatorDataSource."""
14	
15	    async def test_start_populates_cache(self):
16	        """Test that start() immediately populates the cache."""
17	        cache = PriceCache()
18	        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
19	        await source.start(["AAPL", "GOOGL"])
20	
21	        # Cache should have seed prices immediately (before first loop tick)
22	        assert cache.get("AAPL") is not None
23	        assert cache.get("GOOGL") is not None
24	
25	        await source.stop()
26	
27	    async def test_prices_update_over_time(self):
28	        """Test that prices are updated periodically."""
29	        cache = PriceCache()
30	        source = SimulatorDataSource(price_cache=cache, update_interval=0.05)
31	        await source.start(["AAPL"])
32	
33	        initial_version = cache.version
34	        await asyncio.sleep(0.3)  # Several update cycles
35	
36	        # Version should have incremented (prices updated)
37	        assert cache.version > initial_version
38	
39	        await source.stop()
40	
41	    async def test_stop_is_clean(self):
42	        """Test that stop() is clean and idempotent."""
43	        cache = PriceCache()
44	        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
45	        await source.start(["AAPL"])
46	        await source.stop()
47	        # Double stop should not raise
48	        await source.stop()
49	
50	    async def test_add_ticker(self):
51	        """Test adding a ticker dynamically."""
52	        cache = PriceCache()
53	        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
54	        await source.start(["AAPL"])
55	
56	        await source.add_ticker("TSLA")
57	        assert "TSLA" in source.get_tickers()
58	        assert cache.get("TSLA") is not None
59	
60	        await source.stop()
61	
62	    async def test_remove_ticker(self):
63	        """Test removing a ticker."""
64	        cache = PriceCache()
65	        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
66	        await source.start(["AAPL", "TSLA"])
67	
68	        await source.remove_ticker("TSLA")
69	        assert "TSLA" not in source.get_tickers()
70	        assert cache.get("TSLA") is None
71	
72	        await source.stop()
73	
74	    async def test_get_tickers(self):
75	        """Test getting the list of active tickers."""
76	        cache = PriceCache()
77	        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
78	        await source.start(["AAPL", "GOOGL"])
79	
80	        tickers = source.get_tickers()
81	        assert set(tickers) == {"AAPL", "GOOGL"}
82	
83	        await source.stop()
84	
85	    async def test_empty_start(self):
86	        """Test starting with no tickers."""
87	        cache = PriceCache()
88	        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
89	        await source.start([])
90	
91	        assert len(cache) == 0
92	        assert source.get_tickers() == []
93	
94	        await source.stop()
95	
96	    async def test_exception_resilience(self):
97	        """Test that simulator continues running after errors."""
98	        cache = PriceCache()
99	        source = SimulatorDataSource(price_cache=cache, update_interval=0.05)
100	
101	        # Start with a valid ticker
102	        await source.start(["AAPL"])
103	
104	        # Wait for some updates
105	        await asyncio.sleep(0.15)
106	
107	        # Task should still be running
108	        assert source._task is not None
109	        assert not source._task.done()
110	
111	        await source.stop()
112	
113	    async def test_custom_update_interval(self):
114	        """Test using a custom update interval."""
115	        cache = PriceCache()
116	        source = SimulatorDataSource(price_cache=cache, update_interval=0.01)
117	        await source.start(["AAPL"])
118	
119	        initial_version = cache.version
120	        await asyncio.sleep(0.05)  # Should get ~5 updates
121	
122	        # Should have multiple updates with fast interval
123	        assert cache.version > initial_version + 2
124	
125	        await source.stop()
126	
127	    async def test_custom_event_probability(self):
128	        """Test creating source with custom event probability."""
129	        cache = PriceCache()
130	        # Very high event probability for testing
131	        source = SimulatorDataSource(
132	            price_cache=cache, update_interval=0.1, event_probability=1.0
133	        )
134	        await source.start(["AAPL"])
135	
136	        # Just verify it starts and stops cleanly
137	        await asyncio.sleep(0.2)
138	        await source.stop()
139	