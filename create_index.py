from app.database import get_connection

with get_connection() as conn:
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_reservation_per_seat
        ON reservations (seat_id)
        WHERE status IN ('HELD', 'CONFIRMED')
    """)
    row = conn.execute("""
        SELECT indexdef FROM pg_indexes
        WHERE indexname = 'one_active_reservation_per_seat'
    """).fetchone()

print("Index created:", row["indexdef"] if row else "NOT FOUND")
