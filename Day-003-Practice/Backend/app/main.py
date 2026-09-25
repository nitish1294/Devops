import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import RequestContextMiddleware, configure_logging, request_id_var
from app.db.mongo import close_mongo, init_mongo, ping as mongo_ping
from app.db.postgres import engine, init_postgres
from app.services import notifications

configure_logging()
log = logging.getLogger("hrms")

STARTED_AT = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_postgres()
    await init_mongo()
    await notifications.seed_templates()
    log.info(
        "startup complete",
        extra={
            "postgres": f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}",
            "mongo_db": settings.MONGO_DB,
            "smtp": settings.SMTP_HOST or "not configured",
        },
    )

    stop = asyncio.Event()
    worker: asyncio.Task | None = None
    if settings.MAIL_WORKER_ENABLED:
        worker = asyncio.create_task(notifications.outbox_worker(stop))

    try:
        yield
    finally:
        stop.set()
        if worker:
            try:
                await asyncio.wait_for(worker, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                worker.cancel()
        await engine.dispose()
        await close_mongo()
        log.info("shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.1.0",
    description=(
        "Recruitment and hiring platform. PostgreSQL holds the relational record "
        "(requisitions, candidates, pipeline, interviews, offers); MongoDB holds resumes, "
        "scorecards, notes, templates and the audit trail."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Content-Disposition"],
)


def _error(status_code: int, detail: str, **extra) -> JSONResponse:
    body = {"detail": detail, "request_id": request_id_var.get(), **extra}
    return JSONResponse(status_code=status_code, content=body)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    """Turn Pydantic errors into one readable sentence per field for the UI."""
    problems = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err["loc"] if p != "body") or "request"
        problems.append({"field": field, "message": err["msg"]})
    return _error(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "Check the highlighted fields",
        problems=problems,
    )


@app.exception_handler(StarletteHTTPException)
async def http_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    response = _error(exc.status_code, detail)
    for key, value in (exc.headers or {}).items():
        response.headers[key] = value
    return response


@app.exception_handler(IntegrityError)
async def integrity_handler(request: Request, exc: IntegrityError):
    """A constraint fired. That is a client problem, not a server crash."""
    log.warning("integrity error", extra={"error": str(exc.orig)[:200]})
    return _error(
        status.HTTP_409_CONFLICT,
        "That change conflicts with a record which already exists.",
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    """Never leak a traceback to the browser; the request id ties it to the log."""
    log.exception("unhandled error", extra={"path": request.url.path})
    return _error(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Something went wrong on our side. Quote the request id if you report this.",
    )


async def _postgres_up() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
        return True
    except Exception as exc:
        log.warning("postgres health failed", extra={"error": str(exc)[:200]})
        return False


@app.get("/health", tags=["ops"], summary="Full dependency check")
async def health():
    postgres, mongo = await asyncio.gather(_postgres_up(), mongo_ping())
    checks = {
        "postgres": "up" if postgres else "down",
        "mongo": "up" if mongo else "down",
        "mail": "configured" if settings.smtp_configured else "queue only",
    }
    healthy = postgres and mongo
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "ok" if healthy else "degraded",
            "version": app.version,
            "uptime_seconds": int(time.time() - STARTED_AT),
            "checks": checks,
        },
    )


@app.get("/health/live", tags=["ops"], summary="Process is running")
async def liveness():
    """Cheap and dependency-free — a failing database should not get the process
    killed and restarted, which would not fix anything."""
    return {"status": "alive"}


@app.get("/health/ready", tags=["ops"], summary="Ready to serve traffic")
async def readiness():
    postgres, mongo = await asyncio.gather(_postgres_up(), mongo_ping())
    ready = postgres and mongo
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"ready": ready, "postgres": postgres, "mongo": mongo},
    )


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
