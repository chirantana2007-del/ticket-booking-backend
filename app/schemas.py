from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ---------- Seats ----------

class SeatOut(BaseModel):
    seat_id: int
    seat_number: str
    status: Literal["AVAILABLE", "HELD", "BOOKED"]


# ---------- Reservations ----------

class ReservationCreate(BaseModel):
    """Body for POST /reservations"""
    user_id: int = Field(gt=0, examples=[1])
    seat_id: int = Field(gt=0, examples=[20])


class ReservationOut(BaseModel):
    reservation_id: int
    user_id: int
    seat_id: int
    status: Literal["HELD", "CONFIRMED", "EXPIRED", "CANCELLED"]
    created_at: datetime
    expires_at: datetime


class ReservationResponse(BaseModel):
    """Used when an action (reserve / pay / cancel) returns a message + the reservation."""
    message: str
    reservation: ReservationOut


# ---------- Payments (simulated) ----------

class PaymentOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class PaymentRequest(BaseModel):
    """Body for POST /reservations/{id}/pay

    outcome:       whether the fake payment succeeds or fails
    delay_seconds: pretend the payment provider is slow (0 to 10 seconds)
    """
    outcome: PaymentOutcome = PaymentOutcome.SUCCESS
    delay_seconds: int = Field(default=0, ge=0, le=10)