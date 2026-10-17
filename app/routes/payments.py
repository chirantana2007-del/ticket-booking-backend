from fastapi import APIRouter

from app.schemas import PaymentRequest, ReservationResponse
from app.services import payment_service

router = APIRouter(tags=["Payments"])


@router.post("/reservations/{reservation_id}/pay", response_model=ReservationResponse)
def pay(reservation_id: int, body: PaymentRequest):
    res = payment_service.pay_reservation(reservation_id, body.outcome, body.delay_seconds)
    return {"message": "Payment successful. Booking confirmed.", "reservation": res}

