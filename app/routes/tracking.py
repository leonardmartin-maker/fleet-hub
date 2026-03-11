from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.repositories.events_pg import EventRepositoryPG

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/tracking", response_class=HTMLResponse)
def tracking_page(request: Request):
    return templates.TemplateResponse(
        "tracking.html",
        {
            "request": request,
        },
    )


@router.get("/tracking/drivers")
def drivers():
    events = EventRepositoryPG.list()

    drivers = []

    for e in events:
        if e["event_type"] != "shipday.status.received":
            continue

        payload = e.get("payload") or {}

        lat = payload.get("lat")
        lng = payload.get("lng")

        if lat is None or lng is None:
            continue

        drivers.append(
            {
                "orderId": e["order_id"],
                "driverId": payload.get("driverId"),
                "lat": lat,
                "lng": lng,
            }
        )

    return {"drivers": drivers}