from pathlib import Path
import os

CONFIG_PATH = Path(os.getenv("TENANTS_JSON", "tenants.json"))
LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

SHIPDAY_ORDERS_URL = "https://api.shipday.com/orders"
JET_BASE_URL = "https://uk-partnerapi.just-eat.io"