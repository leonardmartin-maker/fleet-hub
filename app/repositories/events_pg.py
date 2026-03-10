from app.db import get_conn


class EventRepositoryPG:

    @staticmethod
    def append(tenant_id, event_type, order_id=None, payload=None):

        with get_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO events (tenant_id,event_type,order_id,payload)
                    VALUES (%s,%s,%s,%s)
                    """,
                    (
                        tenant_id,
                        event_type,
                        order_id,
                        payload or {},
                    ),
                )