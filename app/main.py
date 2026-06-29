from fastapi import FastAPI
from contextlib import asynccontextmanager
from scheduler import start_scheduler, stop_scheduler
from sync import SyncService
from reservation_service import ReservationService
from database import Database
from pms_client import PMSClient

db = Database()
pms = PMSClient()
sync_service = SyncService(db, pms)
service = ReservationService(db, sync_service)

def job():
    service.process_status_changes()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    start_scheduler(job)
    yield

    # shutdown
    stop_scheduler()

app = FastAPI(lifespan=lifespan)