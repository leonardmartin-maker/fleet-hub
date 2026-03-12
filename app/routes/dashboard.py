from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
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

    error = request.query_params.get("error")
    success = request.query_params.get("success")

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "tenants": tenants,
            "orders": orders,
            "error": error,
            "success": success,
        },
    )


@router.post("/dashboard/restaurants/create")
def create_restaurant(
    tenant_id: str = Form(...),
    restaurant_name: str = Form(...),
    justeat_restaurant_id: str = Form(...),
    justeat_webhook_token: str = Form(...),
    shipday_api_key: str = Form(...),
    restaurant_address: str = Form(...),
    restaurant_phone: str = Form(""),
):
    tenant_id = tenant_id.strip().lower()
    restaurant_name = restaurant_name.strip()
    justeat_restaurant_id = justeat_restaurant_id.strip()
    justeat_webhook_token = justeat_webhook_token.strip()
    shipday_api_key = shipday_api_key.strip()
    restaurant_address = restaurant_address.strip()
    restaurant_phone = restaurant_phone.strip()

    data = {
        "justeat": {
            "restaurant_id": justeat_restaurant_id,
            "webhook_token": justeat_webhook_token,
        },
        "shipday": {
            "api_key": shipday_api_key,
        },
        "defaults": {
            "restaurantName": restaurant_name,
            "restaurantAddress": restaurant_address,
            "restaurantPhoneNumber": restaurant_phone,
        },
        "enabled": True,
    }

    existing_tenant = TenantRepositoryPG.get(tenant_id)
    if existing_tenant:
        return RedirectResponse(
            url="/dashboard?error=tenant_exists",
            status_code=303
        )

    existing_jet = TenantRepositoryPG.find_by_justeat_restaurant_id(justeat_restaurant_id)
    if existing_jet:
        return RedirectResponse(
            url="/dashboard?error=justeat_exists",
            status_code=303
        )

    TenantRepositoryPG.upsert(
        tenant_id=tenant_id,
        restaurant_name=restaurant_name,
        data=data,
    )

    return RedirectResponse(url="/dashboard", status_code=303)


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