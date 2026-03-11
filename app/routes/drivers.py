from fastapi import APIRouter
import requests
import os

router = APIRouter()

SHIPDAY_TOKEN = os.getenv("SHIPDAY_TOKEN")


@router.get("/drivers")
def list_drivers():

    url = "https://api.shipday.com/drivers"

    headers = {
        "Authorization": f"Bearer {SHIPDAY_TOKEN}"
    }

    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        return {"drivers": []}

    return r.json()