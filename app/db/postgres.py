from __future__ import annotations

from pathlib import Path

import psycopg2
from sqlalchemy import URL, create_engine
from sqlalchemy.engine import Engine

from app.core.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER, SCHEMA_PATH


def get_postgres_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME,
    )


def get_sqlalchemy_engine() -> Engine:
    return create_engine(
        URL.create(
            "postgresql+psycopg2",
            username=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
        )
    )


def initialize_schema(connection) -> None:
    schema_sql = Path(SCHEMA_PATH).read_text(encoding="utf-8")
    with connection.cursor() as cursor:
        cursor.execute(schema_sql)
