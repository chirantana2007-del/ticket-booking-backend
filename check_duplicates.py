from app.database import get_connection

with get_connection() as conn:
    rows = conn.execute("""
        SELECT seat_id, COUNT(*) AS n
        FROM reservations
        WHERE status IN ('HELD', 'CONFIRMED')
        GROUP BY seat_id
        HAVING COUNT(*) > 1
    """).fetchall()

print("Seats with more than one active reservation:", rows)