1	"""Pytest configuration and fixtures."""
2	
3	import pytest
4	
5	
6	@pytest.fixture
7	def event_loop_policy():
8	    """Use the default event loop policy for all async tests."""
9	    import asyncio
10	
11	    return asyncio.DefaultEventLoopPolicy()
12	