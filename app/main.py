from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.routes import seats, reservations, bookings, payments
from app.services.booking_service import BookingError

app = FastAPI(title="Ticket Booking API", description="Concert with 500 seats")


@app.exception_handler(BookingError)
def booking_error_handler(request: Request, exc: BookingError):
    # One place that turns our business errors into proper HTTP errors.
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.include_router(seats.router)
app.include_router(reservations.router)
app.include_router(bookings.router)
app.include_router(payments.router)


@app.get("/", tags=["Health"])
def home():
    return {"message": "Ticket Booking Backend is running!"}