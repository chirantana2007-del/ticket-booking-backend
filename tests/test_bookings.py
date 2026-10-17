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
