"""FastAPI application factory and lifecycle wiring for FinAlly."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import health, portfolio, watchlist
from app.api.errors import error_response
from app.db import connect, list_watchlist
from app.market import PriceCache, create_market_data_source, create_stream_router
from app.services.portfolio import compute_total_value

logger = logging.getLogger(__name__)

# Project root: app/main.py -> backend -> root.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FRONTEND_OUT = _PROJECT_ROOT / "frontend" / "out"

SNAPSHOT_INTERVAL = 30.0  # seconds


async def _snapshot_loop(app: FastAPI) -> None:
    """Write a portfolio value snapshot every SNAPSHOT_INTERVAL seconds."""
    from app.db import insert_snapshot

    while True:
        await asyncio.sleep(SNAPSHOT_INTERVAL)
        try:
            total = await compute_total_value(app.state.conn, app.state.cache)
            await insert_snapshot(app.state.conn, total)
        except Exception:
            logger.exception("Snapshot loop failed")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: init DB, cache, market source, snapshot task. Shutdown: tear down."""
    load_dotenv(_PROJECT_ROOT / ".env")

    conn = await connect()
    cache = app.state.cache  # created in create_app, shared with the SSE router
    source = create_market_data_source(cache)
    tickers = await list_watchlist(conn)
    await source.start(tickers)

    app.state.conn = conn
    app.state.source = source
    app.state.snapshot_task = asyncio.create_task(_snapshot_loop(app), name="snapshot-loop")

    logger.info("FinAlly started with %d watchlist tickers", len(tickers))
    try:
        yield
    finally:
        app.state.snapshot_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await app.state.snapshot_task
        await source.stop()
        await conn.close()
        logger.info("FinAlly stopped")


def create_app() -> FastAPI:
    """Build and configure the FinAlly FastAPI application."""
    app = FastAPI(title="FinAlly", lifespan=lifespan)
    # One cache instance, shared by the SSE router (bound now) and the market
    # data source (started in lifespan, which reads app.state.cache).
    app.state.cache = PriceCache()

    _register_error_handlers(app)

    app.include_router(health.router)
    app.include_router(portfolio.router)
    app.include_router(watchlist.router)
    # SSE price stream: GET /api/stream/prices. Reads from the same cache.
    app.include_router(create_stream_router(app.state.cache))

    _include_chat_router(app)

    # Serve the Next.js static export at /* when it has been built.
    if _FRONTEND_OUT.is_dir():
        app.mount("/", StaticFiles(directory=_FRONTEND_OUT, html=True), name="frontend")

    return app


def _include_chat_router(app: FastAPI) -> None:
    """Include the LLM chat router if the chat module is present.

    llm-engineer (Task #3) provides app/api/chat.py exposing `router`. This
    keeps the chat layer optional so the API runs and tests pass standalone.
    """
    try:
        from app.api import chat
    except ImportError:
        logger.info("Chat router not present; skipping /api/chat")
        return
    app.include_router(chat.router)


def _register_error_handlers(app: FastAPI) -> None:
    """Render HTTP and validation errors as the {ok, error} envelope."""

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(_request, exc: StarletteHTTPException):
        return error_response(exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_request, exc: RequestValidationError):
        return error_response(400, "Invalid request: " + str(exc.errors()))

    @app.exception_handler(Exception)
    async def _unexpected_handler(_request, exc: Exception):
        logger.exception("Unhandled error")
        return error_response(500, "Internal server error")


app = create_app()
