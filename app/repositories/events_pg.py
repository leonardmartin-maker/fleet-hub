from typing import Any, Dict, List, Optional
from psycopg.types.json import Json
from app.db import get_conn


class EventRepositoryPG:
    @staticmethod
    def append(
        tenant_id: str,
        event_type: str,
        order_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO events (tenant_id, event_type, order_id, payload)
                    VALUES (%s, %s, %s, %s)
                    RETURNING *
                    """,
                    (tenant_id, event_type, order_id, Json(payload or {})),
                )
                return cur.fetchone()

    @staticmethod
    def list() -> List[Dict[str, Any]]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM events
                    ORDER BY id DESC
                    LIMIT 1000
                    """
                )
                return cur.fetchall()

    @staticmethod
    def list_by_tenant(tenant_id: str) -> List[Dict[str, Any]]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM events
                    WHERE tenant_id = %s
                    ORDER BY id DESC
                    LIMIT 500
                    """,
                    (tenant_id,),
                )
                return cur.fetchall()

    @staticmethod
    def list_by_order(order_id: str) -> List[Dict[str, Any]]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM events
                    WHERE order_id = %s
                    ORDER BY id ASC
                    """,
                    (order_id,),
                )
                return cur.fetchall()