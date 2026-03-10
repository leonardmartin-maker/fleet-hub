from fastapi import FastAPI

from app.routes.platform import router as platform_router
from app.routes.justeat import router as justeat_router
from app.routes.shipday import router as shipday_router
from app.workers.retry_worker import retry_worker
import asyncio

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True, "v": "4"}

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(retry_worker())

app.include_router(platform_router)
app.include_router(justeat_router)
app.include_router(shipday_router)

