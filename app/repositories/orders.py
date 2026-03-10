import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ORDERS_FILE = Path("data/orders.jsonl")


class OrderRepository:
    @staticmethod
    def _ensure_file() -> None:
        ORDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not ORDERS_FILE.exists():
            ORDERS_FILE.touch()

    @staticmethod
    def append(order: Dict[str, Any]) -> None:
        OrderRepository._ensure_file()
        with ORDERS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(order, ensure_ascii=False) + "\n")

    @staticmethod
    def list() -> List[Dict[str, Any]]:
        if not ORDERS_FILE.exists():
            return []

        rows: List[Dict[str, Any]] = []
        with ORDERS_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows

    @staticmethod
    def find_by_source(source_order_id: str) -> Optional[Dict[str, Any]]:
        for order in reversed(OrderRepository.list()):
            if str(order.get("sourceOrderId")) == str(source_order_id):
                return order
        return None

    @staticmethod
    def create(tenant_id: str, platform: str, source_order_id: str) -> Dict[str, Any]:
        existing = OrderRepository.find_by_source(source_order_id)
        if existing:
            return existing

        order = {
            "tenantId": tenant_id,
            "sourcePlatform": platform,
            "sourceOrderId": source_order_id,
            "shipdayOrderId": None,
            "createdAt": int(time.time()),
            "status": "received",
        }

        OrderRepository.append(order)
        return order

    @staticmethod
    def mark_shipday_created(source_order_id: str, shipday_order_id: Any) -> Dict[str, Any]:
        order = {
            "sourceOrderId": source_order_id,
            "shipdayOrderId": shipday_order_id,
            "updatedAt": int(time.time()),
            "status": "created",
            "eventType": "shipday.created",
        }
        OrderRepository.append(order)
        return order