from fastapi import APIRouter

from app.schemas import ReservationOut
from app.services import booking_service

router = APIRouter(tags=["Bookings"])


@router.get("/bookings/history", response_model=list[ReservationOut])
def booking_history(user_id: int | None = None):
    """All reservations, newest first. Add ?user_id=1 to see one user's history."""
    return booking_service.list_reservations(user_id)