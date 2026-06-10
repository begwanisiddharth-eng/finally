1	"""Tests for PriceUpdate dataclass."""
2	
3	import pytest
4	
5	from app.market.models import PriceUpdate
6	
7	
8	class TestPriceUpdate:
9	    """Unit tests for the PriceUpdate model."""
10	
11	    def test_price_update_creation(self):
12	        """Test basic PriceUpdate creation."""
13	        update = PriceUpdate(ticker="AAPL", price=190.50, previous_price=190.00, timestamp=1234567890.0)
14	        assert update.ticker == "AAPL"
15	        assert update.price == 190.50
16	        assert update.previous_price == 190.00
17	        assert update.timestamp == 1234567890.0
18	
19	    def test_change_calculation(self):
20	        """Test price change calculation."""
21	        update = PriceUpdate(ticker="AAPL", price=190.50, previous_price=190.00, timestamp=1234567890.0)
22	        assert update.change == 0.50
23	
24	    def test_change_negative(self):
25	        """Test negative price change."""
26	        update = PriceUpdate(ticker="AAPL", price=189.50, previous_price=190.00, timestamp=1234567890.0)
27	        assert update.change == -0.50
28	
29	    def test_change_percent_up(self):
30	        """Test percentage change calculation (up)."""
31	        update = PriceUpdate(ticker="AAPL", price=190.00, previous_price=100.00, timestamp=1234567890.0)
32	        assert update.change_percent == 90.0
33	
34	    def test_change_percent_down(self):
35	        """Test percentage change calculation (down)."""
36	        update = PriceUpdate(ticker="AAPL", price=100.00, previous_price=200.00, timestamp=1234567890.0)
37	        assert update.change_percent == -50.0
38	
39	    def test_change_percent_zero_previous(self):
40	        """Test percentage change with zero previous price."""
41	        update = PriceUpdate(ticker="AAPL", price=100.00, previous_price=0.00, timestamp=1234567890.0)
42	        assert update.change_percent == 0.0
43	
44	    def test_direction_up(self):
45	        """Test direction calculation (up)."""
46	        update = PriceUpdate(ticker="AAPL", price=191.00, previous_price=190.00, timestamp=1234567890.0)
47	        assert update.direction == "up"
48	
49	    def test_direction_down(self):
50	        """Test direction calculation (down)."""
51	        update = PriceUpdate(ticker="AAPL", price=189.00, previous_price=190.00, timestamp=1234567890.0)
52	        assert update.direction == "down"
53	
54	    def test_direction_flat(self):
55	        """Test direction calculation (flat)."""
56	        update = PriceUpdate(ticker="AAPL", price=190.00, previous_price=190.00, timestamp=1234567890.0)
57	        assert update.direction == "flat"
58	
59	    def test_to_dict(self):
60	        """Test serialization to dictionary."""
61	        update = PriceUpdate(ticker="AAPL", price=190.50, previous_price=190.00, timestamp=1234567890.0)
62	        result = update.to_dict()
63	
64	        assert result["ticker"] == "AAPL"
65	        assert result["price"] == 190.50
66	        assert result["previous_price"] == 190.00
67	        assert result["timestamp"] == 1234567890.0
68	        assert result["change"] == 0.50
69	        assert result["change_percent"] == 0.2632  # (0.50 / 190.00) * 100
70	        assert result["direction"] == "up"
71	
72	    def test_immutability(self):
73	        """Test that PriceUpdate is immutable."""
74	        update = PriceUpdate(ticker="AAPL", price=190.50, previous_price=190.00, timestamp=1234567890.0)
75	
76	        with pytest.raises(AttributeError):
77	            update.price = 200.00  # Should raise error
78	