"""Normal booking-flow tests (one request at a time)."""


# ---------- helpers ----------

def reserve(client, user_id, seat_id):
    return client.post("/reservations", json={"user_id": user_id, "seat_id": seat_id})


def pay(client, reservation_id, outcome="SUCCESS", delay_seconds=0):
    return client.post(
        f"/reservations/{reservation_id}/pay",
        json={"outcome": outcome, "delay_seconds": delay_seconds},
    )


def seat_status(client, seat_id):
    seats = client.get("/seats").json()
    return next(s["status"] for s in seats if s["seat_id"] == seat_id)


def expire_hold_in_db(reservation_id):
    """Pretend 10 minutes have passed by moving expires_at into the past."""
    from app.database import get_connection

    with get_connection() as conn:
        conn.execute(
            "UPDATE reservations SET expires_at = NOW() - INTERVAL '10 minutes' "
            "WHERE reservation_id = %s",
            (reservation_id,),
        )


# ---------- tests ----------

def test_view_all_seats(client):
    r = client.get("/seats")
    assert r.status_code == 200
    seats = r.json()
    assert len(seats) == 500
    assert all(s["status"] == "AVAILABLE" for s in seats)


def test_reserve_seat_success(client):
    r = reserve(client, user_id=1, seat_id=10)
    assert r.status_code == 201
    res = r.json()["reservation"]
    assert res["status"] == "HELD"
    assert res["seat_id"] == 10
    assert seat_status(client, 10) == "HELD"


def test_reserve_unavailable_seat_returns_409(client):
    assert reserve(client, 1, 10).status_code == 201
    r = reserve(client, 2, 10)  # a different user wants the same seat
    assert r.status_code == 409


def test_confirm_reservation_after_successful_payment(client):
    reservation_id = reserve(client, 1, 10).json()["reservation"]["reservation_id"]

    r = pay(client, reservation_id, "SUCCESS")
    assert r.status_code == 200
    assert r.json()["reservation"]["status"] == "CONFIRMED"
    assert seat_status(client, 10) == "BOOKED"


def test_payment_failure_keeps_hold_active(client):
    reservation_id = reserve(client, 1, 10).json()["reservation"]["reservation_id"]

    r = pay(client, reservation_id, "FAILURE")
    assert r.status_code == 402

    # The hold is still there, so the user can try again.
    status = client.get(f"/reservations/{reservation_id}").json()["status"]
    assert status == "HELD"
    assert seat_status(client, 10) == "HELD"

    # Retry with a successful payment works.
    assert pay(client, reservation_id, "SUCCESS").status_code == 200


def test_cancel_then_another_user_can_rebook(client):
    reservation_id = reserve(client, 1, 10).json()["reservation"]["reservation_id"]
    assert pay(client, reservation_id).status_code == 200

    r = client.post(f"/reservations/{reservation_id}/cancel")
    assert r.status_code == 200
    assert r.json()["reservation"]["status"] == "CANCELLED"
    assert seat_status(client, 10) == "AVAILABLE"

    # A different user can now take the freed seat.
    r2 = reserve(client, 2, 10)
    assert r2.status_code == 201
    assert r2.json()["reservation"]["user_id"] == 2


def test_expired_hold_makes_seat_available_again(client):
    reservation_id = reserve(client, 1, 10).json()["reservation"]["reservation_id"]
    expire_hold_in_db(reservation_id)

    # The overdue hold is shown as free and reported as EXPIRED.
    assert seat_status(client, 10) == "AVAILABLE"
    assert client.get(f"/reservations/{reservation_id}").json()["status"] == "EXPIRED"

    # Another user can reserve it.
    assert reserve(client, 2, 10).status_code == 201
