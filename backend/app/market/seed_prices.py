1	"""Seed prices and per-ticker parameters for the market simulator."""
2	
3	# Realistic starting prices for the default watchlist (as of project creation)
4	SEED_PRICES: dict[str, float] = {
5	    "AAPL": 190.00,
6	    "GOOGL": 175.00,
7	    "MSFT": 420.00,
8	    "AMZN": 185.00,
9	    "TSLA": 250.00,
10	    "NVDA": 800.00,
11	    "META": 500.00,
12	    "JPM": 195.00,
13	    "V": 280.00,
14	    "NFLX": 600.00,
15	}
16	
17	# Per-ticker GBM parameters
18	# sigma: annualized volatility (higher = more price movement)
19	# mu: annualized drift / expected return
20	TICKER_PARAMS: dict[str, dict[str, float]] = {
21	    "AAPL": {"sigma": 0.22, "mu": 0.05},
22	    "GOOGL": {"sigma": 0.25, "mu": 0.05},
23	    "MSFT": {"sigma": 0.20, "mu": 0.05},
24	    "AMZN": {"sigma": 0.28, "mu": 0.05},
25	    "TSLA": {"sigma": 0.50, "mu": 0.03},  # High volatility
26	    "NVDA": {"sigma": 0.40, "mu": 0.08},  # High volatility, strong drift
27	    "META": {"sigma": 0.30, "mu": 0.05},
28	    "JPM": {"sigma": 0.18, "mu": 0.04},  # Low volatility (bank)
29	    "V": {"sigma": 0.17, "mu": 0.04},  # Low volatility (payments)
30	    "NFLX": {"sigma": 0.35, "mu": 0.05},
31	}
32	
33	# Default parameters for tickers not in the list above (dynamically added)
34	DEFAULT_PARAMS: dict[str, float] = {"sigma": 0.25, "mu": 0.05}
35	
36	# Correlation groups for the simulator's Cholesky decomposition
37	# Tickers in the same group have higher intra-group correlation
38	CORRELATION_GROUPS: dict[str, set[str]] = {
39	    "tech": {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
40	    "finance": {"JPM", "V"},
41	}
42	
43	# Correlation coefficients
44	INTRA_TECH_CORR = 0.6  # Tech stocks move together
45	INTRA_FINANCE_CORR = 0.5  # Finance stocks move together
46	CROSS_GROUP_CORR = 0.3  # Between sectors / unknown tickers
47	TSLA_CORR = 0.3  # TSLA does its own thing
48	