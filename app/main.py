# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the tesa-hostify project.
# See the top-level LICENSE file for the full license text.
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from .database import Database
from .logging_setup import setup_logging
from .monitoring import DiscordNotifier, Heartbeat
from .reservation_service import ReservationService
from .scheduler import start_scheduler, stop_scheduler
from .models import HostifyWebhookPayload
from .config import READ_API_TOKEN, validate_config
from .sync import read_current_lock_codes

setup_logging()
logger = logging.getLogger("main")
discord = DiscordNotifier()
heartbeat = Heartbeat()

db = Database()
service = ReservationService(db)


def status_job():
    heartbeat.ping()
    try:
        service.reconcile()
    except Exception as error:
        logger.error("Scheduled reconciliation failed (%s).", type(error).__name__)
        discord.error(
            title="Scheduled reconciliation failed",
            description="The scheduled reconciliation did not complete. Check application logs.",
        )


def maintenance_job():
    service.delete_old_reservations()
    service.truncate_WAL()


def shutdown():
    service.truncate_WAL()
    heartbeat.close()
    discord.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        validate_config()
    except ValueError as error:
        logger.error("Configuration validation failed: %s", error)
        discord.error(
            title="Configuration validation failed",
            description="Required application configuration is missing or invalid. Check startup logs for variable names.",
        )
        raise
    logger.info("Configuration validation succeeded.")
    try:
        service.reconcile()
    except Exception as error:
        logger.error("Startup reconciliation failed (%s).", type(error).__name__)
        discord.error(
            title="Startup reconciliation failed",
            description="Startup reconciliation did not complete. Check application logs.",
        )
    start_scheduler(status_job, maintenance_job)
    yield
    stop_scheduler(shutdown)


app = FastAPI(lifespan=lifespan)
router = APIRouter()
bearer_auth = HTTPBearer(auto_error=False)


async def require_read_access(
    response: Response,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_auth),
):
    response.headers["Cache-Control"] = "no-store"
    if credentials is None or not secrets.compare_digest(
        credentials.credentials.encode("utf-8"),
        (READ_API_TOKEN or "").encode("utf-8"),
    ):
        raise HTTPException(
            status_code=401,
            detail="A valid bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/api/locks", dependencies=[Depends(require_read_access)])
def get_locks():
    try:
        return read_current_lock_codes()
    except Exception as e:
        logger.error("Failed to read current lock codes: %s", type(e).__name__)
        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve current lock codes from providers.",
        ) from None


@router.get("/api/reservations", dependencies=[Depends(require_read_access)])
def get_upcoming_reservations():
    try:
        reservations = db.list_reservations_checking_out_on_or_after(date.today())
        return {"reservations": reservations}
    except Exception as e:
        logger.error("Failed to read upcoming reservations: %s", type(e).__name__)
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve upcoming reservations.",
        ) from None


@router.post("/webhook/hostify")
async def hostify_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
    except ValueError as e:
        logger.warning("Rejected webhook with malformed JSON.")
        raise HTTPException(status_code=400, detail="Request body must contain valid JSON.") from e

    try:
        validated = HostifyWebhookPayload.model_validate(payload)
    except ValidationError as e:
        logger.warning("Rejected webhook with an invalid payload.")
        raise HTTPException(status_code=422, detail="Webhook payload is invalid.") from e

    event_type = validated.action or "unknown"
    logger.info("Webhook received with action %s.", event_type)

    if not validated.is_supported_reservation_action:
        logger.info("Ignoring webhook action: %s", event_type)
        return {"status": "ignored", "message": f"Action {event_type} is not relevant."}

    if not validated.reservation_id:
        logger.warning("Rejected reservation webhook without reservation_id.")
        raise HTTPException(status_code=422, detail="reservation_id is required.")

    try:
        background_tasks.add_task(service.upsert_reservation, validated.model_dump(exclude_none=True))
    except Exception as e:
        logger.error("Failed to enqueue validated reservation webhook: %s", type(e).__name__)
        discord.error(
            title="Webhook queue failure",
            description="A validated reservation event could not be queued for processing.",
            fields=[{"name": "Action", "value": event_type}],
        )
        raise HTTPException(status_code=500, detail="Failed to process webhook.") from None

    return {"status": "success", "message": "Reservation data is being processed."}


app.include_router(router)
