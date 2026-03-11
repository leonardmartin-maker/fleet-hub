from fastapi import APIRouter
import os
import httpx

router = APIRouter()

SHIPDAY_TOKEN = os.getenv("SHIPDAY_TOKEN")


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