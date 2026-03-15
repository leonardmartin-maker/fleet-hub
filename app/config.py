from pathlib import Path
import os
import logging

# ── Logging ──────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("fleet_hub")

# ── Paths ────────────────────────────────────────────────────────────
CONFIG_PATH = Path(os.getenv("TENANTS_JSON", "data/tenants.json"))
LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Database ─────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://fleet_user:CHANGE_ME_STRONG_PASSWORD@localhost/fleet_hub",
)

# ── External APIs ────────────────────────────────────────────────────
SHIPDAY_ORDERS_URL = "https://api.shipday.com/orders"
SHIPDAY_TOKEN = os.getenv("SHIPDAY_TOKEN", "")
JET_BASE_URL = "https://uk-partnerapi.just-eat.io"

# ── Webhook tokens ───────────────────────────────────────────────────
FLEET_WEBHOOK_TOKEN = os.getenv("FLEET_WEBHOOK_TOKEN", "")