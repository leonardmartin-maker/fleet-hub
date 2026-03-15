import contextlib
from typing import Generator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import DATABASE_URL

pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=2,
    max_size=10,
    kwargs={"row_factory": dict_row},
)


@contextlib.contextmanager
def get_conn() -> Generator[Connection, None, None]:
    """Yield a connection from the pool (auto-committed on exit)."""
    with pool.connection() as conn:
        yield conn
