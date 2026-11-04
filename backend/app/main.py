from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from starlette.exceptions import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from .api import auth, jobs, research, streams, system, workspace
from .core.config import Settings
from .database import make_database
from .middleware import RequestMiddleware, configure_logging


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    engine, sessions = make_database(settings.database_url)
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app):
        # Migrations are an explicit startup step, never runtime create_all.
        yield
        engine.dispose()

    app = FastAPI(title="Retail Fraud Intelligence API", version="1.0.0", description="Synthetic retail transaction generation, fraud detection, robustness evaluation and explanations. All transactions are fictional.", docs_url="/api/v1/docs", openapi_url="/api/v1/openapi.json", redoc_url=None, lifespan=lifespan)
    app.state.settings, app.state.engine, app.state.sessions = settings, engine, sessions
    app.add_middleware(RequestMiddleware, max_bytes=settings.max_json_bytes)
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True, allow_methods=["GET", "POST", "PATCH"], allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "Idempotency-Key", "Last-Event-ID"], expose_headers=["X-Request-ID"])

    def error_response(request, status, code, message, details=None, headers=None):
        return JSONResponse({"error": {"code": code, "message": message, "details": details, "request_id": getattr(request.state, "request_id", None)}}, status_code=status, headers=headers)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error):
        detail = error.detail if isinstance(error.detail, dict) else {"code": "http_error", "message": str(error.detail)}
        return error_response(request, error.status_code, detail.get("code", "http_error"), detail.get("message", "Request failed"), detail.get("details"), error.headers)

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, error):
        # Never echo submitted passwords, tokens, or raw input in validation errors.
        details = [{"location": list(item["loc"]), "message": item["msg"], "type": item["type"]} for item in error.errors()]
        return error_response(request, 422, "validation_error", "Request validation failed.", details)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error):
        logging.getLogger("retail.api").error("database_error", extra={"request_id": getattr(request.state, "request_id", None)})
        return error_response(request, 503, "database_unavailable", "The database could not complete this request.")

    @app.exception_handler(Exception)
    async def unexpected(request: Request, error):
        logging.getLogger("retail.api").error("unexpected_error", extra={"request_id": getattr(request.state, "request_id", None)})
        return error_response(request, 500, "internal_error", "An unexpected server error occurred.")

    for router in (auth.router, research.router, streams.router, workspace.router, jobs.router, system.router):
        app.include_router(router, prefix="/api/v1")
    return app
