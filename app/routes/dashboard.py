from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.repositories.orders_pg import OrderRepositoryPG
from app.repositories.tenants_pg import TenantRepositoryPG
from app.services.order_state import build_order_view

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    tenants = TenantRepositoryPG.list()
    orders = OrderRepositoryPG.list()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "tenants": tenants,
            "orders": orders,
        },
    )


@router.get("/order/{order_id}", response_class=HTMLResponse)
def order_detail(request: Request, order_id: str):
    order = build_order_view(order_id)

    return templates.TemplateResponse(
        "order_detail.html",
        {
            "request": request,
            "order": order,
            "order_id": order_id,
        },
    )