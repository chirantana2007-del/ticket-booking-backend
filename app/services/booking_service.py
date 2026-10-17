from app.database import get_connection, RESERVATION_MINUTES


class BookingError(Exception):
    """A business-rule problem (seat taken, not found, ...).

    The routes will turn this into a proper HTTP error later.
    """

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _release_seat_if_hold_expired(conn, seat):
    """Make a stale hold on this seat available again.

    ONLY call this after you have locked the seat row with FOR UPDATE.
    Returns the seat's real status afterwards.
    """
    if seat["status"] != "HELD":
        return seat["status"]

    # Is there a HELD reservation that has NOT expired yet?
    active_hold = conn.execute("""
        SELECT reservation_id
        FROM reservations
        WHERE seat_id = %s AND status = 'HELD' AND expires_at > NOW()
        FOR UPDATE
    """, (seat["seat_id"],)).fetchone()

    if active_hold is not None:
        return "HELD"

    # No live hold: mark old holds EXPIRED and free the seat.
    conn.execute("""
        UPDATE reservations SET status = 'EXPIRED'
        WHERE seat_id = %s AND status = 'HELD'
    """, (seat["seat_id"],))
    conn.execute("""
        UPDATE seats SET status = 'AVAILABLE'
        WHERE seat_id = %s
    """, (seat["seat_id"],))
    return "AVAILABLE"


def list_seats():
    """Read-only. Shows a seat as AVAILABLE if its hold has run out,
    without writing anything (so viewing seats never blocks bookings)."""
    with get_connection() as conn:
        return conn.execute("""
            SELECT s.seat_id, s.seat_number,
                   CASE
                     WHEN s.status = 'HELD' AND NOT EXISTS (
                         SELECT 1 FROM reservations r
                         WHERE r.seat_id = s.seat_id
                           AND r.status = 'HELD'
                           AND r.expires_at > NOW()
                     ) THEN 'AVAILABLE'
                     ELSE s.status
                   END AS status
            FROM seats s
            ORDER BY s.seat_id
        """).fetchall()


def reserve_seat(user_id: int, seat_id: int):
    with get_connection() as conn:
        # 1. Lock the seat row. If another request already holds this lock,
        #    we WAIT here until it finishes. That is what prevents double booking.
        seat = conn.execute("""
            SELECT seat_id, seat_number, status
            FROM seats
            WHERE seat_id = %s
            FOR UPDATE
        """, (seat_id,)).fetchone()

        if seat is None:
            raise BookingError(404, "Seat not found")

        # 2. If the old hold ran out, free the seat now.
        current_status = _release_seat_if_hold_expired(conn, seat)

        # 3. Still not free? Reject. (Nothing was changed, so rolling back is fine.)
        if current_status != "AVAILABLE":
            raise BookingError(409, "Seat is not available")

        # 4. Create the hold and mark the seat HELD, in ONE transaction.
        reservation = conn.execute("""
            INSERT INTO reservations (user_id, seat_id, status, expires_at)
            VALUES (%s, %s, 'HELD', NOW() + (%s * INTERVAL '1 minute'))
            RETURNING reservation_id, user_id, seat_id,
                      status, created_at, expires_at
        """, (user_id, seat_id, RESERVATION_MINUTES)).fetchone()

        conn.execute("""
            UPDATE seats SET status = 'HELD' WHERE seat_id = %s
        """, (seat_id,))

        return reservation


def _lock_seat_then_reservation(conn, reservation_id):
    """Lock the seat FIRST, then the reservation (same order everywhere,
    so two requests can never wait on each other in a circle = deadlock)."""
    # Peek without locking, only to learn the seat_id. It never changes.
    peek = conn.execute("""
        SELECT seat_id FROM reservations WHERE reservation_id = %s
    """, (reservation_id,)).fetchone()
    if peek is None:
        raise BookingError(404, "Reservation not found")

    seat = conn.execute("""
        SELECT seat_id, seat_number, status
        FROM seats WHERE seat_id = %s FOR UPDATE
    """, (peek["seat_id"],)).fetchone()

    # Re-read AFTER locking: the status may have changed while we waited.
    reservation = conn.execute("""
        SELECT reservation_id, user_id, seat_id, status, created_at, expires_at,
               (expires_at <= NOW()) AS is_expired
        FROM reservations WHERE reservation_id = %s FOR UPDATE
    """, (reservation_id,)).fetchone()
    return seat, reservation


def confirm_reservation(reservation_id: int):
    error = None
    with get_connection() as conn:
        seat, res = _lock_seat_then_reservation(conn, reservation_id)

        if res["status"] == "CONFIRMED":
            res.pop("is_expired")
            return res  # Repeated request: same answer, nothing changes (idempotent)

        if res["status"] in ("EXPIRED", "CANCELLED"):
            error = BookingError(409, f"Reservation is {res['status']}")

        elif res["is_expired"]:
            # Save the expiry FIRST, and raise AFTER the 'with' block ends,
            # so the update is committed instead of rolled back.
            conn.execute("""
                UPDATE reservations SET status = 'EXPIRED'
                WHERE reservation_id = %s
            """, (reservation_id,))
            conn.execute("""
                UPDATE seats SET status = 'AVAILABLE' WHERE seat_id = %s
            """, (res["seat_id"],))
            error = BookingError(409, "Reservation has expired")

        else:
            confirmed = conn.execute("""
                UPDATE reservations SET status = 'CONFIRMED'
                WHERE reservation_id = %s
                RETURNING reservation_id, user_id, seat_id,
                          status, created_at, expires_at
            """, (reservation_id,)).fetchone()
            conn.execute("""
                UPDATE seats SET status = 'BOOKED' WHERE seat_id = %s
            """, (res["seat_id"],))
            return confirmed

    raise error  # the 'with' block has committed by now


def cancel_reservation(reservation_id: int):
    error = None
    with get_connection() as conn:
        seat, res = _lock_seat_then_reservation(conn, reservation_id)

        if res["status"] == "CANCELLED":
            res.pop("is_expired")
            return res  # Repeated request: already cancelled (idempotent)

        if res["status"] == "EXPIRED":
            error = BookingError(409, "Reservation already expired")
        else:
            # HELD or CONFIRMED: cancel it and free the seat.
            cancelled = conn.execute("""
                UPDATE reservations SET status = 'CANCELLED'
                WHERE reservation_id = %s
                RETURNING reservation_id, user_id, seat_id,
                          status, created_at, expires_at
            """, (reservation_id,)).fetchone()
            conn.execute("""
                UPDATE seats SET status = 'AVAILABLE' WHERE seat_id = %s
            """, (res["seat_id"],))
            return cancelled

    raise error



def get_reservation(reservation_id: int):
    with get_connection() as conn:
        row = conn.execute("""
            SELECT reservation_id, user_id, seat_id,
                   CASE WHEN status = 'HELD' AND expires_at <= NOW()
                        THEN 'EXPIRED' ELSE status END AS status,
                   created_at, expires_at
            FROM reservations WHERE reservation_id = %s
        """, (reservation_id,)).fetchone()
    if row is None:
        raise BookingError(404, "Reservation not found")
    return row


def list_reservations(user_id: int | None = None):
    with get_connection() as conn:
        return conn.execute("""
            SELECT reservation_id, user_id, seat_id,
                   CASE WHEN status = 'HELD' AND expires_at <= NOW()
                        THEN 'EXPIRED' ELSE status END AS status,
                   created_at, expires_at
            FROM reservations
            WHERE (%s::int IS NULL OR user_id = %s::int)
            ORDER BY reservation_id DESC
        """, (user_id, user_id)).fetchall()

    