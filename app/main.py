from fastapi import FastAPI

from app.routes.platform import router as platform_router
from app.routes.justeat import router as justeat_router
from app.routes.shipday import router as shipday_router

app = FastAPI()

app.include_router(platform_router)
app.include_router(justeat_router)
app.include_router(shipday_router)