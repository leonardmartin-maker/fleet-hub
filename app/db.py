import os
from psycopg import connect
from psycopg.rows import dict_row

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://fleet_user:CHANGE_ME_STRONG_PASSWORD@localhost/fleet_hub",
)

def get_conn():
    return connect(DATABASE_URL, row_factory=dict_row)