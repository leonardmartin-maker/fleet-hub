from app.db import get_conn


class OrderRepositoryPG:

    @staticmethod
    def create(tenant_id, platform, source_order_id):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO orders (tenant_id, source_platform, source_order_id)
                    VALUES (%s,%s,%s)
                    ON CONFLICT (source_platform, source_order_id)
                    DO NOTHING
                    """,
                    (tenant_id, platform, source_order_id),
                )