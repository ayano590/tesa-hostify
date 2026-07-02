from fastapi import FastAPI, APIRouter, Request, BackgroundTasks
from contextlib import asynccontextmanager
import logging

from database import Database
from reservation_service import ReservationService
from sync import sync_to_tesa
from scheduler import start_scheduler, stop_scheduler
from logging_setup import setup_logging

setup_logging()
logger = logging.getLogger("webhook")
db_logger = logging.getLogger("database")

# --- init core components ---
db = Database()
service = ReservationService(db)

# --- init database ---
db.init_db()

# --- scheduler job wrapper ---
def job():
    service.process_status_changes()
    service.delete_old_reservations()

def shutdown():
    service.close()

# --- FastAPI app with lifespan event ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler(job)
    yield
    stop_scheduler(shutdown)

app = FastAPI(lifespan=lifespan)

router = APIRouter()

# --- Hostify webhook endpoint ---
@router.post("/webhook/hostify")
async def hostify_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
        logger.info(f"Webhook received: payload={payload}")

        if "reservation_id" not in payload:
            return {"status": "error", "reason": "Missing reservation_id in payload"}
        
        background_tasks.add_task(service.upsert_reservation, payload)
        
        return {"status": "success", "message": "Reservation data is being processed."}
    
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {"status": "error", "reason": str(e)}
    
app.include_router(router)