import json
from pathlib import Path

TENANTS_FILE = Path("data/tenants.json")


class TenantRepository:

    @staticmethod
    def load_all():
        if not TENANTS_FILE.exists():
            return {}

        with open(TENANTS_FILE, "r") as f:
            return json.load(f)

    @staticmethod
    def save_all(data):
        TENANTS_FILE.parent.mkdir(exist_ok=True)

        with open(TENANTS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def get(tenant_id):
        tenants = TenantRepository.load_all()
        return tenants.get(tenant_id)

    @staticmethod
    def create(tenant_id, tenant_data):
        tenants = TenantRepository.load_all()

        if tenant_id in tenants:
            raise ValueError("Tenant already exists")

        tenants[tenant_id] = tenant_data

        TenantRepository.save_all(tenants)

        return tenant_data

    @staticmethod
    def list():
        return TenantRepository.load_all()