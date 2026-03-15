from fastapi import APIRouter
import httpx

from app.config import SHIPDAY_TOKEN

router = APIRouter()


@router.get("/drivers")
async def list_drivers():

    url = "https://api.shipday.com/drivers"

    headers = {
        "Authorization": f"Bearer {SHIPDAY_TOKEN}"
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, headers=headers)

    if r.status_code != 200:
        return {"drivers": []}

    return r.json()