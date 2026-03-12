from typing import Any, Dict, List, Optional
from app.db import get_conn


class OrderRepositoryPG:
    @staticmethod
    def create(tenant_id: str, platform: str, source_order_id: str) -> Dict[str, Any]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO orders (tenant_id, source_platform, source_order_id, status, data)
                    VALUES (%s, %s, %s, 'received', '{}'::jsonb)
                    ON CONFLICT (source_platform, source_order_id)
                    DO UPDATE SET source_order_id = EXCLUDED.source_order_id
                    RETURNING *
                    """,
                    (tenant_id, platform, source_order_id),
                )
                return cur.fetchone()

    @staticmethod
    def mark_shipday_created(
        source_order_id: str,
        shipday_order_id: Any,
        shipday_tracking_url: Optional[str] = None,
        shipday_tracking_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE orders
                    SET shipday_order_id = %s,
                        shipday_tracking_url = %s,
                        shipday_tracking_id = %s,
                        status = 'created'
                    WHERE source_order_id = %s
                    RETURNING *
                    """,
                    (
                        str(shipday_order_id),
                        shipday_tracking_url,
                        shipday_tracking_id,
                        source_order_id,
                    ),
                )
                return cur.fetchone()

    @staticmethod
    def find_by_source(source_order_id: str) -> Optional[Dict[str, Any]]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM orders
                    WHERE source_order_id = %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (source_order_id,),
                )
                return cur.fetchone()

    @staticmethod
    def list() -> List[Dict[str, Any]]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM orders
                    ORDER BY id DESC
                    LIMIT 500
                    """
                )
                return cur.fetchall()