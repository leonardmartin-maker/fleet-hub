import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

EVENTS_FILE = Path("data/events.jsonl")


class EventRepository:
    @staticmethod
    def _ensure_file() -> None:
        EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not EVENTS_FILE.exists():
            EVENTS_FILE.touch()

    @staticmethod
    def append(
        tenant_id: str,
        event_type: str,
        order_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        EventRepository._ensure_file()

        event = {
            "ts": int(time.time()),
            "tenantId": tenant_id,
            "eventType": event_type,
            "orderId": order_id,
            "payload": payload or {},
        }

        with EVENTS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        return event

    @staticmethod
    def list() -> List[Dict[str, Any]]:
        if not EVENTS_FILE.exists():
            return []

        rows: List[Dict[str, Any]] = []
        with EVENTS_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows

    @staticmethod
    def list_by_tenant(tenant_id: str) -> List[Dict[str, Any]]:
        return [e for e in EventRepository.list() if e.get("tenantId") == tenant_id]

    @staticmethod
    def list_by_order(order_id: str) -> List[Dict[str, Any]]:
        return [e for e in EventRepository.list() if str(e.get("orderId")) == str(order_id)]