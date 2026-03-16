from typing import Any, Dict, List, Optional
from psycopg.types.json import Json
from app.db import get_conn


class TenantRepositoryPG:

    @staticmethod
    def list() -> List[Dict[str, Any]]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tenant_id, restaurant_name, data
                    FROM tenants
                    ORDER BY tenant_id
                    """
                )
                rows = cur.fetchall()

        tenants = []
        for r in rows:
            tenant = r["data"] or {}
            tenant["tenantId"] = r["tenant_id"]
            tenant["restaurantName"] = r["restaurant_name"]
            tenants.append(tenant)

        return tenants

    @staticmethod
    def get(tenant_id: str) -> Optional[Dict[str, Any]]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tenant_id, restaurant_name, data
                    FROM tenants
                    WHERE tenant_id = %s
                    """,
                    (tenant_id,),
                )
                r = cur.fetchone()

        if not r:
            return None

        tenant = r["data"] or {}
        tenant["tenantId"] = r["tenant_id"]
        tenant["restaurantName"] = r["restaurant_name"]

        return tenant

    @staticmethod
    def upsert(tenant_id: str, restaurant_name: str, data: Dict[str, Any]):

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tenants (tenant_id, restaurant_name, data)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (tenant_id)
                    DO UPDATE SET
                        restaurant_name = EXCLUDED.restaurant_name,
                        data = EXCLUDED.data
                    """,
                    (tenant_id, restaurant_name, Json(data)),
                )
                
    @staticmethod
    def find_by_justeat_restaurant_id(justeat_restaurant_id: str) -> Optional[Dict[str, Any]]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tenant_id, restaurant_name, data
                    FROM tenants
                    WHERE data->'justeat'->>'restaurant_id' = %s
                    LIMIT 1
                    """,
                    (justeat_restaurant_id,),
                )
                r = cur.fetchone()

        if not r:
            return None

        tenant = r["data"] or {}
        tenant["tenantId"] = r["tenant_id"]
        tenant["restaurantName"] = r["restaurant_name"]

        return tenant
    
    @staticmethod
    def find_by_jet_connect_location_id(pos_location_id: str) -> Optional[Dict[str, Any]]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tenant_id, restaurant_name, data
                    FROM tenants
                    WHERE data->'jet_connect'->>'pos_location_id' = %s
                    LIMIT 1
                    """,
                    (pos_location_id,),
                )
                r = cur.fetchone()

        if not r:
            return None

        tenant = r["data"] or {}
        tenant["tenantId"] = r["tenant_id"]
        tenant["restaurantName"] = r["restaurant_name"]

        return tenant

    @staticmethod
    def set_enabled(tenant_id: str, enabled: bool) -> None:
        tenant = TenantRepositoryPG.get(tenant_id)
        if not tenant:
            return

        data = tenant.copy()
        data.pop("tenantId", None)
        data.pop("restaurantName", None)
        data["enabled"] = enabled

        TenantRepositoryPG.upsert(
            tenant_id=tenant_id,
            restaurant_name=tenant["restaurantName"],
            data=data,
        )

    @staticmethod
    def delete(tenant_id: str) -> None:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM tenants
                    WHERE tenant_id = %s
                    """,
                    (tenant_id,),
                )