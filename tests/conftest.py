"""Shared test setup.

Tests run against a SEPARATE database called ticket_booking_test,
so your real data in ticket_booking is never touched.
"""
import os
from pathlib import Path

# Must happen BEFORE app code is imported: point the app at the test database.
# (load_dotenv() does not override variables that are already set.)
TEST_DB = "ticket_booking_test"
os.environ["DB_NAME"] = TEST_DB

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.database import get_connection
from app.main import app

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "docs" / "schema.sql"


def _admin_connection():
    """Connect to the default 'postgres' database (needed to CREATE DATABASE)."""
    return psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname="postgres",
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        autocommit=True,
        connect_timeout=5,
    )


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Create ticket_booking_test (if missing) and load the schema once."""
    with _admin_connection() as admin:
        exists = admin.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,)
        ).fetchone()
        if not exists:
            admin.execute(f'CREATE DATABASE "{TEST_DB}"')

    with get_connection() as conn:
        conn.execute(SCHEMA_FILE.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def clean_tables(test_database):
    """Before every test: empty the test tables and re-seed 500 seats."""
    with get_connection() as conn:
        db_name = conn.execute("SELECT current_database() AS d").fetchone()["d"]
        # Safety lock: never wipe anything that is not a *_test database.
        assert db_name.endswith("_test"), f"Refusing to wipe {db_name!r}"

        conn.execute("TRUNCATE reservations, seats RESTART IDENTITY")
        conn.execute("""
            INSERT INTO seats (seat_number)
            SELECT 'A' || n FROM generate_series(1, 500) AS n
        """)
    yield


@pytest.fixture
def client():
    return TestClient(app)
