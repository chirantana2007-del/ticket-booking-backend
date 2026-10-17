
import os
from datetime import datetime, timezone, timedelta

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="Ticket Booking API")

RESERVATION_MINUTES = 5


def get_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        row_factory=dict_row,
    )


class ReservationRequest(BaseModel):
    user_id: int
    seat_id: int


def release_expired_reservations(conn):
    # Mark expired holds and release their seats.
    conn.execute("""
        UPDATE reservations
        SET status = 'EXPIRED'
        WHERE status = 'HELD'
          AND expires_at <= NOW()
    """)

    conn.execute("""
        UPDATE seats
        SET status = 'AVAILABLE'
        WHERE status = 'HELD'
          AND NOT EXISTS (
              SELECT 1
              FROM reservations r
              WHERE r.seat_id = seats.seat_id
                AND r.status = 'HELD'
                AND r.expires_at > NOW()
          )
    """)


@app.get("/")
def home():
    return {"message": "Ticket Booking Backend is running!"}


@app.get("/seats")
def get_seats():
    with get_connection() as conn:
        release_expired_reservations(conn)

        seats = conn.execute("""
            SELECT seat_id, seat_number, status
            FROM seats
            ORDER BY seat_id
        """).fetchall()

        return seats


@app.post("/reservations")
def reserve_seat(request: ReservationRequest):
    with get_connection() as conn:
        # Lock the requested seat so concurrent requests
        # cannot both reserve it successfully.
        seat = conn.execute("""
            SELECT seat_id, seat_number, status
            FROM seats
            WHERE seat_id = %s
            FOR UPDATE
        """, (request.seat_id,)).fetchone()

        if seat is None:
            raise HTTPException(
                status_code=404,
                detail="Seat not found"
            )

        # The lock is held while we check expiry and reserve.
        release_expired_reservations(conn)

        seat = conn.execute("""
            SELECT seat_id, seat_number, status
            FROM seats
            WHERE seat_id = %s
        """, (request.seat_id,)).fetchone()

        if seat["status"] != "AVAILABLE":
            raise HTTPException(
                status_code=409,
                detail="Seat is not available"
            )

        reservation = conn.execute("""
            INSERT INTO reservations
                (user_id, seat_id, status, expires_at)
            VALUES
                (%s, %s, 'HELD', NOW() + (%s * INTERVAL '1 minute'))
            RETURNING reservation_id, user_id, seat_id,
                      status, created_at, expires_at
        """, (
            request.user_id,
            request.seat_id,
            RESERVATION_MINUTES
        )).fetchone()

        conn.execute("""
            UPDATE seats
            SET status = 'HELD'
            WHERE seat_id = %s
        """, (request.seat_id,))

        return {
            "message": "Seat reserved successfully",
            "reservation": reservation
        }


@app.get("/reservations/{reservation_id}")
def get_reservation(reservation_id: int):
    with get_connection() as conn:
        release_expired_reservations(conn)

        reservation = conn.execute("""
            SELECT reservation_id, user_id, seat_id,
                   status, created_at, expires_at
            FROM reservations
            WHERE reservation_id = %s
        """, (reservation_id,)).fetchone()

        if reservation is None:
            raise HTTPException(
                status_code=404,
                detail="Reservation not found"
            )

        return reservation

@app.post("/reservations/{reservation_id}/confirm")
def confirm_reservation(reservation_id: int):
    with get_connection() as conn:
        # Find and lock the reservation.
        reservation = conn.execute("""
            SELECT reservation_id, seat_id, status, expires_at
            FROM reservations
            WHERE reservation_id = %s
            FOR UPDATE
        """, (reservation_id,)).fetchone()

        if reservation is None:
            raise HTTPException(
                status_code=404,
                detail="Reservation not found"
            )

        # Check whether the hold has expired.
        if reservation["status"] != "HELD":
            raise HTTPException(
                status_code=409,
                detail="Reservation is not active"
            )

        if reservation["expires_at"] <= datetime.now(timezone.utc):
            conn.execute("""
                UPDATE reservations
                SET status = 'EXPIRED'
                WHERE reservation_id = %s
            """, (reservation_id,))

            conn.execute("""
                UPDATE seats
                SET status = 'AVAILABLE'
                WHERE seat_id = %s
            """, (reservation["seat_id"],))

            raise HTTPException(
                status_code=409,
                detail="Reservation has expired"
            )

        # Mark the reservation as confirmed.
        conn.execute("""
            UPDATE reservations
            SET status = 'CONFIRMED'
            WHERE reservation_id = %s
        """, (reservation_id,))

        conn.execute("""
            UPDATE seats
            SET status = 'BOOKED'
            WHERE seat_id = %s
        """, (reservation["seat_id"],))

        return {
            "message": "Booking confirmed successfully",
            "reservation_id": reservation_id,
            "seat_id": reservation["seat_id"],
            "status": "CONFIRMED"
        }
