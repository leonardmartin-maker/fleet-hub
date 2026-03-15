import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import logger
from app.db import pool
from app.workers.retry_worker import retry_worker

from app.routes.platform import router as platform_router
from app.routes.justeat import router as justeat_router
from app.routes.shipday import router as shipday_router
from app.routes.dashboard import router as dashboard_router
from app.routes.tracking import router as tracking_router
from app.routes.drivers import router as drivers_router
from app.routes.dispatch import router as dispatch_router
from app.routes.shipday_client import router as shipday_client_router
from app.routes.shipday_fleet import router as shipday_fleet_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Fleet Hub starting up")
    task = asyncio.create_task(retry_worker())
    yield
    task.cancel()
    pool.close()
    logger.info("Fleet Hub shut down")


app = FastAPI(title="Fleet Hub", version="5.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "detail": str(exc)},
    )


app.include_router(platform_router)
app.include_router(justeat_router)
app.include_router(shipday_router)
app.include_router(dashboard_router)
app.include_router(tracking_router)
app.include_router(drivers_router)
app.include_router(dispatch_router)
app.include_router(shipday_client_router)
app.include_router(shipday_fleet_router)
