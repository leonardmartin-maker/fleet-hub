from typing import Any, Dict, Tuple
from fastapi import HTTPException
import json

from app.config import CONFIG_PATH


def load_tenants() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise RuntimeError(f"Missing tenants config: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise RuntimeError("tenants.json must be an object {tenant_id: {...}}")
    return data


def get_tenant(tenant_id: str) -> Dict[str, Any]:
    tenants = load_tenants()
    tenant = tenants.get(tenant_id)
    if not isinstance(tenant, dict):
        raise HTTPException(status_code=404, detail="Unknown tenant")
    return tenant


def find_tenant_by_justeat_restaurant_id(restaurant_id: str) -> Tuple[str, Dict[str, Any]]:
    tenants = load_tenants()
    for tenant_id, tenant in tenants.items():
        justeat = tenant.get("justeat") or {}
        if str(justeat.get("restaurant_id", "")).strip() == str(restaurant_id).strip():
            return tenant_id, tenant
    raise HTTPException(status_code=404, detail="Unknown JustEat restaurant_id")