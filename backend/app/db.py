import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://copiloto:copiloto@localhost:5433/copiloto")


@contextmanager
def conn():
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as c:
        yield c


def query(sql: str, params: tuple | dict = ()) -> list[dict]:
    with conn() as c:
        return c.execute(sql, params).fetchall()
