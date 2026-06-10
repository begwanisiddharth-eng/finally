1	"""Tests for market data source factory."""
2	
3	import os
4	from unittest.mock import patch
5	
6	from app.market.cache import PriceCache
7	from app.market.factory import create_market_data_source
8	from app.market.massive_client import MassiveDataSource
9	from app.market.simulator import SimulatorDataSource
10	
11	
12	class TestFactory:
13	    """Tests for create_market_data_source factory."""
14	
15	    def test_creates_simulator_when_no_api_key(self):
16	        """Test that simulator is created when MASSIVE_API_KEY is not set."""
17	        cache = PriceCache()
18	
19	        with patch.dict(os.environ, {}, clear=True):
20	            source = create_market_data_source(cache)
21	
22	        assert isinstance(source, SimulatorDataSource)
23	
24	    def test_creates_simulator_when_api_key_empty(self):
25	        """Test that simulator is created when MASSIVE_API_KEY is empty."""
26	        cache = PriceCache()
27	
28	        with patch.dict(os.environ, {"MASSIVE_API_KEY": ""}, clear=True):
29	            source = create_market_data_source(cache)
30	
31	        assert isinstance(source, SimulatorDataSource)
32	
33	    def test_creates_simulator_when_api_key_whitespace(self):
34	        """Test that simulator is created when MASSIVE_API_KEY is whitespace."""
35	        cache = PriceCache()
36	
37	        with patch.dict(os.environ, {"MASSIVE_API_KEY": "   "}, clear=True):
38	            source = create_market_data_source(cache)
39	
40	        assert isinstance(source, SimulatorDataSource)
41	
42	    def test_creates_massive_when_api_key_set(self):
43	        """Test that Massive client is created when MASSIVE_API_KEY is set."""
44	        cache = PriceCache()
45	
46	        with patch.dict(os.environ, {"MASSIVE_API_KEY": "test-key"}, clear=True):
47	            source = create_market_data_source(cache)
48	
49	        assert isinstance(source, MassiveDataSource)
50	
51	    def test_massive_receives_api_key(self):
52	        """Test that Massive client receives the API key."""
53	        cache = PriceCache()
54	
55	        with patch.dict(os.environ, {"MASSIVE_API_KEY": "test-key-123"}, clear=True):
56	            source = create_market_data_source(cache)
57	
58	        assert isinstance(source, MassiveDataSource)
59	        assert source._api_key == "test-key-123"
60	
61	    def test_simulator_receives_cache(self):
62	        """Test that simulator receives the cache reference."""
63	        cache = PriceCache()
64	
65	        with patch.dict(os.environ, {}, clear=True):
66	            source = create_market_data_source(cache)
67	
68	        assert isinstance(source, SimulatorDataSource)
69	        assert source._cache is cache
70	
71	    def test_massive_receives_cache(self):
72	        """Test that Massive client receives the cache reference."""
73	        cache = PriceCache()
74	
75	        with patch.dict(os.environ, {"MASSIVE_API_KEY": "test-key"}, clear=True):
76	            source = create_market_data_source(cache)
77	
78	        assert isinstance(source, MassiveDataSource)
79	        assert source._cache is cache
80	