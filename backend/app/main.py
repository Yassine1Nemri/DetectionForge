import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import router
from app.core.config import get_settings
from app.services.sigma_service import DomainError

app = FastAPI(
    title="DetectionForge",
    version="0.1.0",
    description="Phase 1: Sigma engineering and offline fixture testing",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def limit_request(request: Request, call_next):
    # Bound actual streamed bytes, including requests without Content-Length.
    if request.method in {"POST", "PUT", "PATCH"}:
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 2_000_000:
                return JSONResponse(
                    {"error": {"code": "payload_too_large", "message": "Request exceeds 2 MB"}},
                    status_code=413,
                )
        request._body = bytes(body)
    return await call_next(request)


@app.exception_handler(DomainError)
async def domain_error(_: Request, exc: DomainError):
    return JSONResponse({"error": {"code": "domain_error", "message": exc.message}}, status_code=exc.status)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    details = [{"location": list(e["loc"]), "message": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse(
        {
            "error": {
                "code": "validation_error",
                "message": "; ".join(e["message"] for e in details),
                "details": details,
            }
        },
        status_code=422,
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(_: Request, exc: SQLAlchemyError):
    logging.getLogger("detectionforge").error("Database operation failed (%s)", type(exc).__name__)
    return JSONResponse(
        {
            "error": {
                "code": "database_error",
                "message": "Database unavailable or schema missing. Check server configuration and migrations.",
            }
        },
        status_code=503,
    )


app.include_router(router)
