from fastapi import FastAPI, APIRouter, Request
from contextlib import asynccontextmanager
import logging

from database import Database
from reservation_service import ReservationService
from sync import sync_to_tesa
from scheduler import start_scheduler, stop_scheduler
from logging_setup import setup_logging

setup_logging()
logger = logging.getLogger("webhook")

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

router = APIRouter()

# --- Hostify webhook endpoint ---
@router.post("/webhook/hostify")
async def hostify_webhook(request: Request):
    try:
        payload = await request.json()
        logger.info(f"Webhook received: hostify_id={payload.get('hostify_id')}")

        if "hostify_id" not in payload:
            return {"status": "error", "reason": "Missing hostify_id in payload"}
        
        return service.upsert_reservation(payload)
    
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {"status": "error", "reason": str(e)}
    
app.include_router(router)