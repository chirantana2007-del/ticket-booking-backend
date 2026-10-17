from fastapi import APIRouter

from app.schemas import SeatOut
from app.services import booking_service

router = APIRouter(tags=["Seats"])


@router.get("/seats", response_model=list[SeatOut])
def get_seats():
    return booking_service.list_seats()