import json
from app.repositories.tenants_pg import TenantRepositoryPG

with open("tenants.json") as f:
    tenants = json.load(f)

for tenant_id, tenant in tenants.items():

    restaurant_name = tenant.get("restaurantName")

    TenantRepositoryPG.upsert(
        tenant_id=tenant_id,
        restaurant_name=restaurant_name,
        data=tenant
    )

print("Tenants migrated")