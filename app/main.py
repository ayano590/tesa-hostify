from fastapi import FastAPI
from contextlib import asynccontextmanager
from database import Database
from reservation_service import ReservationService
from sync import sync_to_tesa
from scheduler import start_scheduler, stop_scheduler

# --- init core components ---
db = Database()
service = ReservationService(db, sync_to_tesa)

# --- scheduler job wrapper ---
def job():
    service.process_status_changes()

# --- FastAPI app with lifespan event ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler(job)
    yield
    stop_scheduler()

app = FastAPI(lifespan=lifespan)

# --- Hostify webhook endpoint ---
@app.post("/webhook/hostify")
def hostify_webhook(payload: dict):
    service.upsert_reservation(payload)
    return {"status": "success"}