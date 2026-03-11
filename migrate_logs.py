import json
from pathlib import Path

from app.repositories.events_pg import EventRepositoryPG

LOG_DIR = Path("/var/log/fleet-webhooks/tenants")


def migrate_file(path: Path, tenant_id: str, event_type: str):

    if not path.exists():
        return 0

    count = 0

    with path.open() as f:
        for line in f:

            try:
                data = json.loads(line)
            except Exception:
                continue

            order_id = data.get("orderId") or data.get("order_id")

            EventRepositoryPG.append(
                tenant_id=tenant_id,
                event_type=event_type,
                order_id=order_id,
                payload=data,
            )

            count += 1

    return count


def main():

    total = 0

    for tenant_dir in LOG_DIR.iterdir():

        if not tenant_dir.is_dir():
            continue

        tenant_id = tenant_dir.name

        total += migrate_file(
            tenant_dir / "justeat_in.jsonl",
            tenant_id,
            "justeat.order.received",
        )

        total += migrate_file(
            tenant_dir / "shipday_events.jsonl",
            tenant_id,
            "shipday.status.received",
        )

        total += migrate_file(
            tenant_dir / "shipday_create.jsonl",
            tenant_id,
            "shipday.order.created",
        )

        total += migrate_file(
            tenant_dir / "justeat_out.jsonl",
            tenant_id,
            "justeat.status.sent",
        )

    print(f"Migrated {total} events")


if __name__ == "__main__":
    main()