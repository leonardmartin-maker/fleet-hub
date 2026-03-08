import json
from collections import Counter, defaultdict
from pathlib import Path

path = Path("/var/log/fleet-webhooks/shipday_events.jsonl")
c = Counter()
orders = set()
drivers = set()
unknown = 0

# pour voir les valeurs raw les plus fréquentes
raw_status = Counter()

with path.open("r", encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        obj = json.loads(line)
        c[obj.get("normalizedStatus", "missing")] += 1

        payload = obj.get("payload", {}) or {}
        raw = payload.get("status") or payload.get("event") or payload.get("deliveryStatus") or "missing"
        raw_status[str(raw).strip().lower()] += 1

        if obj.get("orderId"):
            orders.add(obj["orderId"])

        # best-effort driver id extraction in payload (same heuristics)
        driver = payload.get("driver") or payload.get("rider") or {}
        did = payload.get("driverId") or payload.get("driver_id") or (driver.get("id") if isinstance(driver, dict) else None)
        if did:
            drivers.add(str(did))

        if obj.get("normalizedStatus") in ("unknown", None, "missing"):
            unknown += 1

print("=== Shipday events stats ===")
print("Total events:", sum(c.values()))
print("Unique orders:", len(orders))
print("Unique drivers:", len(drivers))
print("\nNormalized status counts:")
for k, v in c.most_common():
    print(f"  {k}: {v}")

print("\nTop raw status values:")
for k, v in raw_status.most_common(20):
    print(f"  {k}: {v}")
