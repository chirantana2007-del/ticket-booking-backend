import psycopg.errors

from app.database import get_connection

conn = get_connection()
try:
    active = conn.execute("""
        SELECT reservation_id, seat_id, user_id, status
        FROM reservations
        WHERE status IN ('HELD', 'CONFIRMED')
        LIMIT 1
    """).fetchone()

    if active is None:
        print("No active reservation found. Reserve a seat in Swagger first, then re-run.")
        raise SystemExit(0)

    print("Existing active reservation:", active)
    print("Trying to insert a SECOND active reservation for seat", active["seat_id"], "...")

    try:
        conn.execute("""
            INSERT INTO reservations (seat_id, user_id, status, expires_at)
            VALUES (%s, %s, 'HELD', NOW() + INTERVAL '5 minutes')
        """, (active["seat_id"], active["user_id"] + 1000))
        print("PROBLEM: the insert was accepted. The index is NOT protecting you!")
    except psycopg.errors.UniqueViolation as e:
        print("GOOD: PostgreSQL refused it with UniqueViolation.")
        print("   ", str(e).splitlines()[0])
finally:
    conn.rollback()   # the test row is never saved, whatever happened
    conn.close()
    print("Rolled back. Nothing was written.")
