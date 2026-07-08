from fastapi import FastAPI, APIRouter, Request, BackgroundTasks
from contextlib import asynccontextmanager
import logging

from database import Database
from reservation_service import ReservationService
from scheduler import start_scheduler, stop_scheduler
from logging_setup import setup_logging
from monitoring import DiscordNotifier

setup_logging()
logger = logging.getLogger("webhook")
discord = DiscordNotifier()

discord.info(title="Server start", description="")

# --- init core components ---
db = Database()
service = ReservationService(db)

# --- init database ---
try:
    db.init_db()
except Exception as e:
    discord.error(title="Database Initialization Error", description=str(e))
    logger.error(f"Error initializing database: {e}")

# --- scheduler job wrapper ---
def job():
    service.process_status_changes()
    service.delete_old_reservations()

def shutdown():
    discord.info(title="Server stop", description="")
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
        logger.info(f"Webhook received.")

        event_type = payload["action"]

        if event_type not in ["new_reservation", "update_reservation", "move_reservation"]:
            logger.info(f"Ignoring webhook action: {event_type}")
            return {"status": "ignored", "message": f"Action {event_type} is not relevant."}
        
        background_tasks.add_task(service.upsert_reservation, payload)
        
        return {"status": "success", "message": "Reservation data is being processed."}
    
    except Exception as e:
        discord.error(title="Webhook Processing Error", description=str(e))
        logger.error(f"Error processing webhook: {e}")
        return {"status": "error", "reason": str(e)}
    
app.include_router(router)