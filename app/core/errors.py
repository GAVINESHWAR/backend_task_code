"""Consistent error envelope: {success, message, code}."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def error_payload(message: str, code: str) -> dict:
    return {"success": False, "message": message, "code": code}


def ok_payload(data=None, message: str = "OK") -> dict:
    return {"success": True, "message": message, "data": data}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_handler(_: Request, exc: StarletteHTTPException):
        code = getattr(exc, "code", None) or f"HTTP_{exc.status_code}"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(str(exc.detail), str(code)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=error_payload("Validation failed.", "VALIDATION_ERROR")
            | {"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, __: Exception):
        # Never leak stack traces to the client.
        return JSONResponse(
            status_code=500,
            content=error_payload("An unexpected error occurred.", "INTERNAL_ERROR"),
        )
