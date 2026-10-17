from fastapi import APIRouter

from app.schemas import ReservationCreate, ReservationOut, ReservationResponse
from app.services import booking_service

router = APIRouter(tags=["Reservations"])


@router.post("/reservations", response_model=ReservationResponse, status_code=201)
def create_reservation(body: ReservationCreate):
    res = booking_service.reserve_seat(body.user_id, body.seat_id)
    return {"message": "Seat held. Pay before the hold expires.", "reservation": res}


@router.get("/reservations/{reservation_id}", response_model=ReservationOut)
def get_reservation(reservation_id: int):
    return booking_service.get_reservation(reservation_id)


@router.post("/reservations/{reservation_id}/cancel", response_model=ReservationResponse)
def cancel_reservation(reservation_id: int):
    res = booking_service.cancel_reservation(reservation_id)
    return {"message": "Reservation cancelled. Seat is available again.", "reservation": res}