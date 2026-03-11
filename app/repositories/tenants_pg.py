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