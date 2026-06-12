"""Shared async lock serializing multi-step database writes.

The app uses a single aiosqlite connection whose commits are connection-global.
Operations that do a read-modify-write across several statements (trade
execution, reset) or that must observe a consistent snapshot (the periodic
portfolio snapshot) hold this lock so they cannot interleave with one another.
"""

from __future__ import annotations

import asyncio

db_write_lock = asyncio.Lock()
