1	"""Data models for market data."""
2	
3	from __future__ import annotations
4	
5	import time
6	from dataclasses import dataclass, field
7	
8	
9	@dataclass(frozen=True, slots=True)
10	class PriceUpdate:
11	    """Immutable snapshot of a single ticker's price at a point in time."""
12	
13	    ticker: str
14	    price: float
15	    previous_price: float
16	    timestamp: float = field(default_factory=time.time)  # Unix seconds
17	
18	    @property
19	    def change(self) -> float:
20	        """Absolute price change from previous update."""
21	        return round(self.price - self.previous_price, 4)
22	
23	    @property
24	    def change_percent(self) -> float:
25	        """Percentage change from previous update."""
26	        if self.previous_price == 0:
27	            return 0.0
28	        return round((self.price - self.previous_price) / self.previous_price * 100, 4)
29	
30	    @property
31	    def direction(self) -> str:
32	        """'up', 'down', or 'flat'."""
33	        if self.price > self.previous_price:
34	            return "up"
35	        elif self.price < self.previous_price:
36	            return "down"
37	        return "flat"
38	
39	    def to_dict(self) -> dict:
40	        """Serialize for JSON / SSE transmission."""
41	        return {
42	            "ticker": self.ticker,
43	            "price": self.price,
44	            "previous_price": self.previous_price,
45	            "timestamp": self.timestamp,
46	            "change": self.change,
47	            "change_percent": self.change_percent,
48	            "direction": self.direction,
49	        }
50	