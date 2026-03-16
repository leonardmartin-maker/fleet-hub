"""Repository for fleet configurations stored in PostgreSQL.

Table schema (run once on the DB):
    CREATE TABLE IF NOT EXISTS fleets (
        fleet_id TEXT PRIMARY KEY,
        fleet_name TEXT NOT NULL,
        data JSONB NOT NULL DEFAULT '{}'
    );
"""

from typing import Any, Dict, List, Optional

from psycopg.types.json import Json

from app.db import get_conn


class FleetRepositoryPG:

    @staticmethod
    def list() -> List[Dict[str, Any]]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT fleet_id, fleet_name, data
                    FROM fleets
                    ORDER BY fleet_id
                    """
                )
                rows = cur.fetchall()

        result = []
        for r in rows:
            fleet = r["data"] or {}
            fleet["fleetId"] = r["fleet_id"]
            fleet["fleetName"] = r["fleet_name"]
            result.append(fleet)

        return result

    @staticmethod
    def get(fleet_id: str) -> Optional[Dict[str, Any]]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT fleet_id, fleet_name, data
                    FROM fleets
                    WHERE fleet_id = %s
                    """,
                    (fleet_id,),
                )
                r = cur.fetchone()

        if not r:
            return None

        fleet = r["data"] or {}
        fleet["fleetId"] = r["fleet_id"]
        fleet["fleetName"] = r["fleet_name"]
        return fleet

    @staticmethod
    def get_default() -> Optional[Dict[str, Any]]:
        """Return the first fleet (used as default when there's only one)."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT fleet_id, fleet_name, data
                    FROM fleets
                    ORDER BY fleet_id
                    LIMIT 1
                    """
                )
                r = cur.fetchone()

        if not r:
            return None

        fleet = r["data"] or {}
        fleet["fleetId"] = r["fleet_id"]
        fleet["fleetName"] = r["fleet_name"]
        return fleet

    @staticmethod
    def upsert(fleet_id: str, fleet_name: str, data: Dict[str, Any]):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO fleets (fleet_id, fleet_name, data)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (fleet_id)
                    DO UPDATE SET
                        fleet_name = EXCLUDED.fleet_name,
                        data = EXCLUDED.data
                    """,
                    (fleet_id, fleet_name, Json(data)),
                )

    @staticmethod
    def delete(fleet_id: str) -> None:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM fleets
                    WHERE fleet_id = %s
                    """,
                    (fleet_id,),
                )

    @staticmethod
    def ensure_table() -> None:
        """Create the fleets table if it doesn't exist."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS fleets (
                        fleet_id TEXT PRIMARY KEY,
                        fleet_name TEXT NOT NULL,
                        data JSONB NOT NULL DEFAULT '{}'
                    )
                    """
                )
