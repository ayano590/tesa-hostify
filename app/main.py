# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the tesa-hostify project.
# See the top-level LICENSE file for the full license text.
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, BackgroundTasks, FastAPI, Request

from database import Database
from logging_setup import setup_logging
from monitoring import DiscordNotifier, Heartbeat
from reservation_service import ReservationService
from scheduler import start_scheduler, stop_scheduler
from models import HostifyWebhookPayload

setup_logging()
logger = logging.getLogger("main")
discord = DiscordNotifier()
heartbeat = Heartbeat()

discord.info(title="Server start", description="")

db = Database()
service = ReservationService(db)


def status_job():
    heartbeat.ping()
    service.reconcile()


def maintenance_job():
    service.delete_old_reservations()
    service.truncate_WAL()


def shutdown():
    service.truncate_WAL()
    discord.info(title="Server stop", description="")


@asynccontextmanager
async def lifespan(app: FastAPI):
    service.reconcile()
    start_scheduler(status_job, maintenance_job)
    yield
    stop_scheduler(shutdown)


app = FastAPI(lifespan=lifespan)
router = APIRouter()


@router.post("/webhook/hostify")
async def hostify_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
        logger.info("Webhook received.")

        validated = HostifyWebhookPayload.model_validate(payload)
        event_type = validated.action or "unknown"

        if event_type not in ["new_reservation", "update_reservation", "move_reservation"]:
            logger.info(f"Ignoring webhook action: {event_type}")
            return {"status": "ignored", "message": f"Action {event_type} is not relevant."}

        if not validated.reservation_id:
            raise ValueError("reservation_id is required")

        background_tasks.add_task(service.upsert_reservation, payload)
        return {"status": "success", "message": "Reservation data is being processed."}
    except Exception as e:
        discord.error(title="Webhook Processing Error", description=str(e))
        logger.error(f"Error processing webhook: {e}")
        return {"status": "error", "reason": str(e)}


app.include_router(router)
