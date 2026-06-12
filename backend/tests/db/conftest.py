"""Fixtures for database tests: a fresh temp-file DB per test."""

import pytest_asyncio

from app.db import connect


@pytest_asyncio.fixture
async def conn(tmp_path):
    """Open a connection to a fresh temp DB (schema + seed applied), closed after."""
    connection = await connect(tmp_path / "test.db")
    yield connection
    await connection.close()
