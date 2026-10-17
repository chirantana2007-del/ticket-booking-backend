import time

from app.schemas import PaymentOutcome
from app.database import get_connection
from app.services.booking_service import BookingError, confirm_reservation


def pay_reservation(reservation_id: int, outcome: PaymentOutcome, delay_seconds: int):
    # ---- Phase 1: quick check, then release the connection ----
    with get_connection() as conn:
        res = conn.execute("""
            SELECT reservation_id, user_id, seat_id, status, created_at, expires_at,
                   (expires_at <= NOW()) AS is_expired
            FROM reservations WHERE reservation_id = %s
        """, (reservation_id,)).fetchone()

    if res is None:
        raise BookingError(404, "Reservation not found")

    if res["status"] == "CONFIRMED":
        res.pop("is_expired")
        return res  # Repeated payment request: already paid, nothing changes

    if res["status"] != "HELD":
        raise BookingError(409, f"Reservation is {res['status']}")

    if res["is_expired"]:
        raise BookingError(409, "Reservation has expired")

    # ---- Phase 2: the "slow payment provider". NO database lock is held here. ----
    if delay_seconds > 0:
        time.sleep(delay_seconds)

    # ---- Phase 3: payment finished ----
    if outcome == PaymentOutcome.FAILURE:
        raise BookingError(
            402,
            "Payment failed. Your hold stays active until it expires, so you can try again.",
        )

    # SUCCESS: confirm_reservation re-locks the seat and re-checks everything,
    # because the hold may have expired or been cancelled during the delay.
    return confirm_reservation(reservation_id)