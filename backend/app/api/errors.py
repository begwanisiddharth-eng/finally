"""Error envelope helpers."""

from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import JSONResponse


def error_response(status_code: int, message: str) -> JSONResponse:
    """Build a JSON error envelope: {"ok": false, "error": "..."}."""
    return JSONResponse(status_code=status_code, content={"ok": False, "error": message})


class ApiError(HTTPException):
    """HTTPException whose detail is rendered as the error envelope."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(status_code=status_code, detail=message)
