1	"""Tests for PriceCache."""
2	
3	from app.market.cache import PriceCache
4	
5	
6	class TestPriceCache:
7	    """Unit tests for the PriceCache."""
8	
9	    def test_update_and_get(self):
10	        """Test updating and getting a price."""
11	        cache = PriceCache()
12	        update = cache.update("AAPL", 190.50)
13	        assert update.ticker == "AAPL"
14	        assert update.price == 190.50
15	        assert cache.get("AAPL") == update
16	
17	    def test_first_update_is_flat(self):
18	        """Test that the first update has flat direction."""
19	        cache = PriceCache()
20	        update = cache.update("AAPL", 190.50)
21	        assert update.direction == "flat"
22	        assert update.previous_price == 190.50
23	
24	    def test_direction_up(self):
25	        """Test price update with upward direction."""
26	        cache = PriceCache()
27	        cache.update("AAPL", 190.00)
28	        update = cache.update("AAPL", 191.00)
29	        assert update.direction == "up"
30	        assert update.change == 1.00
31	
32	    def test_direction_down(self):
33	        """Test price update with downward direction."""
34	        cache = PriceCache()
35	        cache.update("AAPL", 190.00)
36	        update = cache.update("AAPL", 189.00)
37	        assert update.direction == "down"
38	        assert update.change == -1.00
39	
40	    def test_remove(self):
41	        """Test removing a ticker from cache."""
42	        cache = PriceCache()
43	        cache.update("AAPL", 190.00)
44	        cache.remove("AAPL")
45	        assert cache.get("AAPL") is None
46	
47	    def test_remove_nonexistent(self):
48	        """Test removing a ticker that doesn't exist."""
49	        cache = PriceCache()
50	        cache.remove("AAPL")  # Should not raise
51	
52	    def test_get_all(self):
53	        """Test getting all prices."""
54	        cache = PriceCache()
55	        cache.update("AAPL", 190.00)
56	        cache.update("GOOGL", 175.00)
57	        all_prices = cache.get_all()
58	        assert set(all_prices.keys()) == {"AAPL", "GOOGL"}
59	
60	    def test_version_increments(self):
61	        """Test that version counter increments."""
62	        cache = PriceCache()
63	        v0 = cache.version
64	        cache.update("AAPL", 190.00)
65	        assert cache.version == v0 + 1
66	        cache.update("AAPL", 191.00)
67	        assert cache.version == v0 + 2
68	
69	    def test_get_price_convenience(self):
70	        """Test the convenience get_price method."""
71	        cache = PriceCache()
72	        cache.update("AAPL", 190.50)
73	        assert cache.get_price("AAPL") == 190.50
74	        assert cache.get_price("NOPE") is None
75	
76	    def test_len(self):
77	        """Test __len__ method."""
78	        cache = PriceCache()
79	        assert len(cache) == 0
80	        cache.update("AAPL", 190.00)
81	        assert len(cache) == 1
82	        cache.update("GOOGL", 175.00)
83	        assert len(cache) == 2
84	
85	    def test_contains(self):
86	        """Test __contains__ method."""
87	        cache = PriceCache()
88	        cache.update("AAPL", 190.00)
89	        assert "AAPL" in cache
90	        assert "GOOGL" not in cache
91	
92	    def test_custom_timestamp(self):
93	        """Test updating with a custom timestamp."""
94	        cache = PriceCache()
95	        custom_ts = 1234567890.0
96	        update = cache.update("AAPL", 190.50, timestamp=custom_ts)
97	        assert update.timestamp == custom_ts
98	
99	    def test_price_rounding(self):
100	        """Test that prices are rounded to 2 decimal places."""
101	        cache = PriceCache()
102	        update = cache.update("AAPL", 190.12345)
103	        assert update.price == 190.12
104	