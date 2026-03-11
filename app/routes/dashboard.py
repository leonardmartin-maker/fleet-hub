from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.repositories.orders_pg import OrderRepositoryPG
from app.repositories.tenants_pg import TenantRepositoryPG

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