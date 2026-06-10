1	"""Tests for GBMSimulator."""
2	
3	from app.market.seed_prices import SEED_PRICES
4	from app.market.simulator import GBMSimulator
5	
6	
7	class TestGBMSimulator:
8	    """Unit tests for the GBM price simulator."""
9	
10	    def test_step_returns_all_tickers(self):
11	        """Test that step() returns prices for all tickers."""
12	        sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
13	        result = sim.step()
14	        assert set(result.keys()) == {"AAPL", "GOOGL"}
15	
16	    def test_prices_are_positive(self):
17	        """GBM prices can never go negative (exp() is always positive)."""
18	        sim = GBMSimulator(tickers=["AAPL"])
19	        for _ in range(10_000):
20	            prices = sim.step()
21	            assert prices["AAPL"] > 0
22	
23	    def test_initial_prices_match_seeds(self):
24	        """Test that initial prices match seed prices."""
25	        sim = GBMSimulator(tickers=["AAPL"])
26	        # Before any step, price should be the seed price
27	        assert sim.get_price("AAPL") == SEED_PRICES["AAPL"]
28	
29	    def test_add_ticker(self):
30	        """Test adding a ticker dynamically."""
31	        sim = GBMSimulator(tickers=["AAPL"])
32	        sim.add_ticker("TSLA")
33	        result = sim.step()
34	        assert "TSLA" in result
35	
36	    def test_remove_ticker(self):
37	        """Test removing a ticker."""
38	        sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
39	        sim.remove_ticker("GOOGL")
40	        result = sim.step()
41	        assert "GOOGL" not in result
42	        assert "AAPL" in result
43	
44	    def test_add_duplicate_is_noop(self):
45	        """Test that adding a duplicate ticker is a no-op."""
46	        sim = GBMSimulator(tickers=["AAPL"])
47	        sim.add_ticker("AAPL")
48	        assert len(sim._tickers) == 1
49	
50	    def test_remove_nonexistent_is_noop(self):
51	        """Test that removing a non-existent ticker is a no-op."""
52	        sim = GBMSimulator(tickers=["AAPL"])
53	        sim.remove_ticker("NOPE")  # Should not raise
54	
55	    def test_unknown_ticker_gets_random_seed_price(self):
56	        """Test that unknown tickers get random seed prices."""
57	        sim = GBMSimulator(tickers=["ZZZZ"])
58	        price = sim.get_price("ZZZZ")
59	        assert price is not None
60	        assert 50.0 <= price <= 300.0
61	
62	    def test_empty_step(self):
63	        """Test stepping with no tickers."""
64	        sim = GBMSimulator(tickers=[])
65	        result = sim.step()
66	        assert result == {}
67	
68	    def test_prices_change_over_time(self):
69	        """After many steps, prices should have drifted from their seeds."""
70	        sim = GBMSimulator(tickers=["AAPL"])
71	        initial_price = sim.get_price("AAPL")
72	
73	        for _ in range(1000):
74	            sim.step()
75	
76	        final_price = sim.get_price("AAPL")
77	        # Price should have changed (extremely unlikely to be exactly the seed)
78	        assert final_price != initial_price
79	
80	    def test_cholesky_rebuilds_on_add(self):
81	        """Test that Cholesky matrix is rebuilt when tickers are added."""
82	        sim = GBMSimulator(tickers=["AAPL"])
83	        assert sim._cholesky is None  # Only 1 ticker, no correlation matrix
84	        sim.add_ticker("GOOGL")
85	        assert sim._cholesky is not None  # Now 2 tickers, matrix exists
86	
87	    def test_cholesky_none_with_one_ticker(self):
88	        """Test that Cholesky is None with only one ticker."""
89	        sim = GBMSimulator(tickers=["AAPL"])
90	        assert sim._cholesky is None
91	
92	    def test_get_price_returns_none_for_unknown(self):
93	        """Test that get_price returns None for unknown ticker."""
94	        sim = GBMSimulator(tickers=["AAPL"])
95	        assert sim.get_price("UNKNOWN") is None
96	
97	    def test_pairwise_correlation_tech_stocks(self):
98	        """Test that tech stocks have high correlation."""
99	        corr = GBMSimulator._pairwise_correlation("AAPL", "GOOGL")
100	        assert corr == 0.6
101	
102	    def test_pairwise_correlation_finance_stocks(self):
103	        """Test that finance stocks have moderate correlation."""
104	        corr = GBMSimulator._pairwise_correlation("JPM", "V")
105	        assert corr == 0.5
106	
107	    def test_pairwise_correlation_tsla(self):
108	        """Test that TSLA has lower correlation with everything."""
109	        corr = GBMSimulator._pairwise_correlation("TSLA", "AAPL")
110	        assert corr == 0.3
111	        corr = GBMSimulator._pairwise_correlation("TSLA", "JPM")
112	        assert corr == 0.3
113	
114	    def test_pairwise_correlation_cross_sector(self):
115	        """Test cross-sector correlation."""
116	        corr = GBMSimulator._pairwise_correlation("AAPL", "JPM")
117	        assert corr == 0.3
118	
119	    def test_default_dt_is_reasonable(self):
120	        """Test that default dt is a reasonable small value."""
121	        assert 0 < GBMSimulator.DEFAULT_DT < 0.0001
122	
123	    def test_prices_rounded_to_two_decimals(self):
124	        """Test that prices are rounded to 2 decimal places."""
125	        sim = GBMSimulator(tickers=["AAPL"])
126	        result = sim.step()
127	        price_str = str(result["AAPL"])
128	        # Check that we have at most 2 decimal places
129	        if '.' in price_str:
130	            decimal_part = price_str.split('.')[1]
131	            assert len(decimal_part) <= 2
132	