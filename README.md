# Ticket Booking Backend

A FastAPI + PostgreSQL backend for booking seats at a 500-seat concert.

## Features
- View seats, reserve a seat with a 5-minute hold, pay (simulated success, failure, delay), cancel, and view history
- Double booking prevented with row-level locking (`SELECT ... FOR UPDATE`)
- Repeated confirm, cancel and pay requests are safe (idempotent)
- Swagger docs at `/docs`

## Run locally
1. Create a `.env` file with DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
2. `pip install -r requirements.txt`
3. `uvicorn app.main:app --reload`
4. Open http://127.0.0.1:8000/docs

## Endpoints
- `GET /seats`
- `POST /reservations`
- `GET /reservations/{id}`
- `POST /reservations/{id}/pay`
- `POST /reservations/{id}/cancel`
- `GET /bookings/history`

## Status
Work in progress. Still to come: automated tests, Docker setup, diagrams, and a database-level unique index.