from typing import Any, Dict, List, Optional
from psycopg.types.json import Json

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
    def mark_shipday_created(source_order_id: str, shipday_order_id: Any) -> Optional[Dict[str, Any]]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE orders
                    SET shipday_order_id = %s,
                        status = 'created'
                    WHERE source_order_id = %s
                    RETURNING *
                    """,
                    (str(shipday_order_id), source_order_id),
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
    def find_by_shipday_order_id(shipday_order_id: Any) -> Optional[Dict[str, Any]]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM orders
                    WHERE shipday_order_id = %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (str(shipday_order_id),),
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

    @staticmethod
    def update_status(source_order_id: str, status: str) -> None:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE orders
                    SET status = %s
                    WHERE source_order_id = %s
                    """,
                    (status, source_order_id),
                )

    @staticmethod
    def update_driver(
        source_order_id: str,
        driver_id: str,
        lat: float | None,
        lng: float | None,
    ) -> None:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE orders
                    SET driver_id = %s,
                        driver_lat = %s,
                        driver_lng = %s,
                        driver_last_seen_at = NOW()
                    WHERE source_order_id = %s
                    """,
                    (driver_id, lat, lng, source_order_id),
                )

    @staticmethod
    def update_metadata(
        source_order_id: str,
        shipday_order_id: Any = None,
        shipday_tracking_url: str | None = None,
        shipday_tracking_id: str | None = None,
        data: Dict[str, Any] | None = None,
    ) -> None:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE orders
                    SET shipday_order_id = COALESCE(%s, shipday_order_id),
                        shipday_tracking_url = COALESCE(%s, shipday_tracking_url),
                        shipday_tracking_id = COALESCE(%s, shipday_tracking_id),
                        data = COALESCE(%s::jsonb, data)
                    WHERE source_order_id = %s
                    """,
                    (
                        str(shipday_order_id) if shipday_order_id is not None else None,
                        shipday_tracking_url,
                        shipday_tracking_id,
                        Json(data) if data is not None else None,
                        source_order_id,
                    ),
                )

    @staticmethod
    def clear_driver(source_order_id: str):

        with get_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE orders
                    SET
                        driver_id = NULL,
                        driver_lat = NULL,
                        driver_lng = NULL,
                        driver_last_seen_at = NULL
                    WHERE source_order_id = %s
                    """,
                    (source_order_id,)
                )