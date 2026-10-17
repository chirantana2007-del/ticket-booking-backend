import os

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

RESERVATION_MINUTES = 5


def get_connection():
    """Open a new database connection.

    Use it like this:

        with get_connection() as conn:
            conn.execute(...)

    When the 'with' block ends normally, everything is COMMITTED.
    If an error is raised inside it, everything is ROLLED BACK.
    The connection is closed either way.
    """
    return psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        row_factory=dict_row,
        connect_timeout=5,
    )


if __name__ == "__main__":
    # Quick self-test: python -m app.database
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM seats").fetchone()
        print(f"Database connected! Total seats: {row['total']}")