1	"""Tests for MassiveDataSource (mocked)."""
2	
3	from unittest.mock import MagicMock, patch
4	
5	import pytest
6	
7	from app.market.cache import PriceCache
8	from app.market.massive_client import MassiveDataSource
9	
10	
11	def _make_snapshot(ticker: str, price: float, timestamp_ms: int) -> MagicMock:
12	    """Create a mock Massive snapshot object."""
13	    snap = MagicMock()
14	    snap.ticker = ticker
15	    snap.last_trade = MagicMock()
16	    snap.last_trade.price = price
17	    snap.last_trade.timestamp = timestamp_ms
18	    return snap
19	
20	
21	@pytest.mark.asyncio
22	class TestMassiveDataSource:
23	    """Unit tests for MassiveDataSource with mocked API."""
24	
25	    async def test_poll_updates_cache(self):
26	        """Test that polling updates the cache."""
27	        cache = PriceCache()
28	        source = MassiveDataSource(
29	            api_key="test-key",
30	            price_cache=cache,
31	            poll_interval=60.0,  # Long interval so the loop doesn't auto-poll
32	        )
33	        source._tickers = ["AAPL", "GOOGL"]
34	        source._client = MagicMock()  # Satisfy the _poll_once guard
35	
36	        mock_snapshots = [
37	            _make_snapshot("AAPL", 190.50, 1707580800000),
38	            _make_snapshot("GOOGL", 175.25, 1707580800000),
39	        ]
40	
41	        with patch.object(source, "_fetch_snapshots", return_value=mock_snapshots):
42	            await source._poll_once()
43	
44	        assert cache.get_price("AAPL") == 190.50
45	        assert cache.get_price("GOOGL") == 175.25
46	
47	    async def test_malformed_snapshot_skipped(self):
48	        """Test that malformed snapshots are skipped gracefully."""
49	        cache = PriceCache()
50	        source = MassiveDataSource(
51	            api_key="test-key",
52	            price_cache=cache,
53	            poll_interval=60.0,
54	        )
55	        source._tickers = ["AAPL", "BAD"]
56	        source._client = MagicMock()  # Satisfy the _poll_once guard
57	
58	        good_snap = _make_snapshot("AAPL", 190.50, 1707580800000)
59	        bad_snap = MagicMock()
60	        bad_snap.ticker = "BAD"
61	        bad_snap.last_trade = None  # Will cause AttributeError
62	
63	        with patch.object(source, "_fetch_snapshots", return_value=[good_snap, bad_snap]):
64	            await source._poll_once()
65	
66	        # Good ticker processed, bad one skipped
67	        assert cache.get_price("AAPL") == 190.50
68	        assert cache.get_price("BAD") is None
69	
70	    async def test_api_error_does_not_crash(self):
71	        """Test that API errors don't crash the poller."""
72	        cache = PriceCache()
73	        source = MassiveDataSource(
74	            api_key="test-key",
75	            price_cache=cache,
76	            poll_interval=60.0,
77	        )
78	        source._tickers = ["AAPL"]
79	        source._client = MagicMock()  # Satisfy the _poll_once guard
80	
81	        with patch.object(source, "_fetch_snapshots", side_effect=Exception("network error")):
82	            await source._poll_once()  # Should not raise
83	
84	        assert cache.get_price("AAPL") is None  # No update happened
85	
86	    async def test_timestamp_conversion(self):
87	        """Test that timestamps are converted from milliseconds to seconds."""
88	        cache = PriceCache()
89	        source = MassiveDataSource(
90	            api_key="test-key",
91	            price_cache=cache,
92	            poll_interval=60.0,
93	        )
94	        source._tickers = ["AAPL"]
95	        source._client = MagicMock()  # Satisfy the _poll_once guard
96	
97	        mock_snapshots = [_make_snapshot("AAPL", 190.50, 1707580800000)]
98	
99	        with patch.object(source, "_fetch_snapshots", return_value=mock_snapshots):
100	            await source._poll_once()
101	
102	        update = cache.get("AAPL")
103	        assert update is not None
104	        assert update.timestamp == 1707580800.0  # Converted to seconds
105	
106	    async def test_add_ticker(self):
107	        """Test adding a ticker."""
108	        cache = PriceCache()
109	        source = MassiveDataSource(api_key="test-key", price_cache=cache)
110	
111	        await source.add_ticker("AAPL")
112	        assert "AAPL" in source.get_tickers()
113	
114	    async def test_add_ticker_uppercase_normalization(self):
115	        """Test that tickers are normalized to uppercase."""
116	        cache = PriceCache()
117	        source = MassiveDataSource(api_key="test-key", price_cache=cache)
118	
119	        await source.add_ticker("aapl")
120	        assert "AAPL" in source.get_tickers()
121	
122	    async def test_add_ticker_strips_whitespace(self):
123	        """Test that ticker whitespace is stripped."""
124	        cache = PriceCache()
125	        source = MassiveDataSource(api_key="test-key", price_cache=cache)
126	
127	        await source.add_ticker("  AAPL  ")
128	        assert "AAPL" in source.get_tickers()
129	
130	    async def test_remove_ticker(self):
131	        """Test removing a ticker."""
132	        cache = PriceCache()
133	        source = MassiveDataSource(api_key="test-key", price_cache=cache)
134	        source._tickers = ["AAPL", "GOOGL"]
135	        cache.update("AAPL", 190.00)
136	
137	        await source.remove_ticker("AAPL")
138	        assert "AAPL" not in source.get_tickers()
139	        assert cache.get("AAPL") is None
140	
141	    async def test_get_tickers(self):
142	        """Test getting the list of active tickers."""
143	        cache = PriceCache()
144	        source = MassiveDataSource(api_key="test-key", price_cache=cache)
145	        source._tickers = ["AAPL", "GOOGL"]
146	
147	        tickers = source.get_tickers()
148	        assert tickers == ["AAPL", "GOOGL"]
149	
150	    async def test_empty_tickers_skips_poll(self):
151	        """Test that polling is skipped when there are no tickers."""
152	        cache = PriceCache()
153	        source = MassiveDataSource(api_key="test-key", price_cache=cache)
154	        source._tickers = []
155	
156	        # Should not call _fetch_snapshots
157	        with patch.object(source, "_fetch_snapshots") as mock_fetch:
158	            await source._poll_once()
159	            mock_fetch.assert_not_called()
160	
161	    async def test_stop_is_idempotent(self):
162	        """Test that stop() can be called multiple times."""
163	        cache = PriceCache()
164	        source = MassiveDataSource(api_key="test-key", price_cache=cache)
165	
166	        await source.stop()
167	        await source.stop()  # Should not raise
168	
169	    async def test_stop_cancels_task(self):
170	        """Test that stop() cancels the polling task."""
171	        cache = PriceCache()
172	        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=10.0)
173	
174	        # Mock the client and start
175	        with patch("app.market.massive_client.RESTClient"):
176	            with patch.object(source, "_fetch_snapshots", return_value=[]):
177	                await source.start(["AAPL"])
178	
179	        # Verify task is running
180	        assert source._task is not None
181	        assert not source._task.done()
182	
183	        # Stop and verify task is cancelled
184	        await source.stop()
185	        assert source._task is None
186	
187	    async def test_start_immediate_poll(self):
188	        """Test that start() does an immediate poll before starting the loop."""
189	        cache = PriceCache()
190	        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
191	
192	        mock_snapshots = [_make_snapshot("AAPL", 190.50, 1707580800000)]
193	
194	        with patch("app.market.massive_client.RESTClient"):
195	            with patch.object(source, "_fetch_snapshots", return_value=mock_snapshots):
196	                await source.start(["AAPL"])
197	
198	        # Cache should have data immediately from the first poll
199	        assert cache.get_price("AAPL") == 190.50
200	
201	        await source.stop()
202	