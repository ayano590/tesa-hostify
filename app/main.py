# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the tesa-hostify project.
# See the top-level LICENSE file for the full license text.
from fastapi import (
    FastAPI,
    APIRouter,
    Request,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
)
from contextlib import asynccontextmanager
from datetime import date, datetime
import csv
from io import StringIO
from json import JSONDecodeError
import hmac
import logging

from app.config import READ_API_TOKEN
from app.database import Database
from app.reservation_service import ReservationService
from app.scheduler import start_scheduler, stop_scheduler
from app.sync import read_current_tesa_pins, read_current_ttlock_door_codes
from app.logging_setup import setup_logging
from app.monitoring import DiscordNotifier, Heartbeat

setup_logging()
logger = logging.getLogger("main")
discord = DiscordNotifier()
heartbeat = Heartbeat()

# --- init core components ---
db = Database()
service = ReservationService(db)

# --- scheduler job wrapper ---
def status_job():
    heartbeat.ping()
    service.process_status_changes()

def maintenance_job():
    service.delete_old_reservations()
    service.truncate_WAL()

def shutdown():
    service.truncate_WAL()

# --- FastAPI app with lifespan event ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler(status_job, maintenance_job)
    yield
    stop_scheduler(shutdown)

app = FastAPI(lifespan=lifespan)

router = APIRouter()

def require_read_access(authorization: str = Header(default="")):
    if not READ_API_TOKEN or len(READ_API_TOKEN) < 32:
        raise HTTPException(status_code=503, detail="Read API access is not configured.")

    scheme, separator, token = authorization.partition(" ")
    if (
        not separator
        or scheme.lower() != "bearer"
        or not hmac.compare_digest(token.encode("utf-8"), READ_API_TOKEN.encode("utf-8"))
    ):
        raise HTTPException(status_code=401, detail="Invalid API token.")

@router.get("/api/reservations", dependencies=[Depends(require_read_access)])
def get_active_reservations():
    try:
        now = datetime.now()
        reservations = []
        for reservation in db.list_all_reservations():
            status = service._compute_status(reservation, now)
            if status == "active":
                reservations.append({
                    "reservation_id": reservation["reservation_id"],
                    "room_number": reservation["room_number"],
                    "check_in": reservation["check_in"],
                    "check_out": reservation["check_out"],
                    "lifecycle_status": status,
                    "door_code": reservation["door_code"],
                })
        return {"reservations": reservations}
    except Exception as e:
        logger.error("Failed to read active reservations: %s", type(e).__name__)
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve active reservations.",
        ) from e

@router.get("/api/ttlock-pins", dependencies=[Depends(require_read_access)])
def get_current_ttlock_pins():
    return read_current_ttlock_door_codes()

@router.get("/api/tesa-pins", dependencies=[Depends(require_read_access)])
def get_current_tesa_pins():
    return read_current_tesa_pins()

@router.post("/api/reservations/report", dependencies=[Depends(require_read_access)])
def send_reservation_report():
    try:
        today = date.today()
        upcoming = [
            (reservation, datetime.fromisoformat(reservation["check_in"]))
            for reservation in db.list_all_reservations()
            if datetime.fromisoformat(reservation["check_in"]).date() >= today
        ]
        upcoming.sort(key=lambda item: item[1])
        reservations = [reservation for reservation, _ in upcoming[:30]]
        reservations.sort(key=lambda reservation: (
            str(reservation.get("reservation_id") or ""),
            str(reservation.get("room_number") or ""),
            datetime.fromisoformat(reservation["check_in"]),
            datetime.fromisoformat(reservation["check_out"]),
            str(reservation.get("door_code") or ""),
        ))
    except Exception as e:
        logger.error("Failed to prepare reservation report: %s", type(e).__name__)
        raise HTTPException(
            status_code=500,
            detail="Unable to prepare the reservation report.",
        ) from e

    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["booking_number", "room_number", "check_in", "check_out", "door_code"])
    for reservation in reservations:
        writer.writerow([
            reservation.get("reservation_id") or "",
            reservation.get("room_number") or "",
            reservation.get("check_in") or "",
            reservation.get("check_out") or "",
            reservation.get("door_code") or "",
        ])

    filename = f"reservation-dates-{date.today().isoformat()}.csv"
    if not discord.send_file(
        title=f"Reservation dates ({len(reservations)} bookings)",
        filename=filename,
        content=output.getvalue(),
    ):
        raise HTTPException(
            status_code=503,
            detail="Unable to send the reservation CSV to Discord.",
        )
    return {"status": "sent", "count": len(reservations)}

def _notify_malformed_webhook(request: Request, category: str, reason: str, action: str):
    fields = [
        {"name": "Method", "value": request.method},
        {"name": "Path", "value": request.url.path},
        {"name": "Content-Type", "value": request.headers.get("content-type", "missing")},
        {"name": "Action", "value": action[:100]},
    ]
    discord.error(
        title=f"Hostify webhook {category}",
        description=reason[:1000],
        fields=fields,
    )
    logger.warning("Rejected Hostify webhook (%s): %s", category, reason)

def _validate_reservation_payload(payload: dict):
    required_shapes = [
        ("reservation_id", (), (str, int)),
        ("data", (), (dict,)),
        ("data.listing", ("data",), (dict,)),
        ("data.listing.nickname", ("data", "listing"), (str,)),
        ("data.reservation", ("data",), (dict,)),
        ("data.reservation.checkIn", ("data", "reservation"), (str,)),
        ("data.reservation.checkOut", ("data", "reservation"), (str,)),
        ("data.reservation.planned_arrival", ("data", "reservation"), (str, type(None))),
        ("data.reservation.planned_departure", ("data", "reservation"), (str, type(None))),
        ("data.reservation.status", ("data", "reservation"), (str,)),
        ("data.reservation.custom_fields", ("data", "reservation"), (list,)),
        ("data.guest", ("data",), (dict,)),
        ("data.guest.name", ("data", "guest"), (str,)),
    ]

    for field_path, parent_path, expected_types in required_shapes:
        parent = payload
        for key in parent_path:
            parent = parent[key]
        key = field_path.rsplit(".", 1)[-1]
        if key not in parent:
            return "missing required key", f"Missing required key: {field_path}."
        if not isinstance(parent[key], expected_types) or isinstance(parent[key], bool):
            expected = " or ".join(expected_type.__name__ for expected_type in expected_types)
            return "wrong payload shape", f"{field_path} must be {expected}."

    reservation = payload["data"]["reservation"]
    for field_path, date_key, time_key, default_time in (
        ("data.reservation.checkIn", "checkIn", "planned_arrival", "14:00:00"),
        ("data.reservation.checkOut", "checkOut", "planned_departure", "10:00:00"),
    ):
        planned_time = reservation[time_key]
        if planned_time in ("00:00:00", "None", None, ""):
            planned_time = default_time
        try:
            datetime.fromisoformat(f"{reservation[date_key]}T{planned_time}")
        except ValueError:
            return "wrong payload shape", f"{field_path} and {time_key} must form a valid date and time."

    custom_fields = reservation["custom_fields"]
    door_code = None
    for index, custom_field in enumerate(custom_fields):
        if not isinstance(custom_field, dict):
            return "wrong payload shape", f"data.reservation.custom_fields[{index}] must be an object."
        if "name" not in custom_field:
            return "missing required key", f"Missing required key: data.reservation.custom_fields[{index}].name."
        if not isinstance(custom_field["name"], str):
            return "wrong payload shape", f"data.reservation.custom_fields[{index}].name must be a string."
        if custom_field["name"] == "door_code":
            if "value" not in custom_field or custom_field["value"] in (None, ""):
                return "missing door_code", "The door_code custom field has no value."
            if not isinstance(custom_field["value"], (str, int)) or isinstance(custom_field["value"], bool):
                return "wrong payload shape", "The door_code custom field value must be a string or integer."
            door_code = custom_field["value"]

    if door_code is None:
        return "missing door_code", "No door_code custom field was provided."
    return None

# --- Hostify webhook endpoint ---
@router.post("/webhook/hostify")
async def hostify_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
        logger.info(f"Webhook received.")
    except (JSONDecodeError, UnicodeDecodeError) as e:
        reason = f"Invalid JSON: {e}"
        _notify_malformed_webhook(request, "malformed payload", reason, "<unavailable>")
        return {"status": "error", "reason": reason}

    if not isinstance(payload, dict):
        reason = "Valid JSON must be an object."
        _notify_malformed_webhook(request, "malformed payload", reason, "<unavailable>")
        return {"status": "error", "reason": reason}

    if "action" not in payload:
        reason = "Missing required action."
        _notify_malformed_webhook(request, "malformed payload", reason, "<missing>")
        return {"status": "error", "reason": reason}

    event_type = payload["action"]
    if not isinstance(event_type, str) or event_type not in [
        "new_reservation",
        "update_reservation",
        "move_reservation",
    ]:
        reason = "Invalid or unsupported action."
        action = event_type if isinstance(event_type, str) else f"<{type(event_type).__name__}>"
        _notify_malformed_webhook(request, "malformed payload", reason, action)
        return {"status": "error", "reason": reason}

    validation_error = _validate_reservation_payload(payload)
    if validation_error:
        category, reason = validation_error
        action = payload["action"]
        _notify_malformed_webhook(request, category, reason, action)
        return {"status": "error", "reason": reason}

    nickname = payload["data"]["listing"]["nickname"]
    digit_count = sum(char.isdigit() for char in nickname)
    if digit_count != 1:
        reason = (
            "Listing nickname must contain exactly one digit; "
            f"received {digit_count}."
        )
        _notify_malformed_webhook(
            request, "invalid room nickname", reason, payload["action"]
        )
        return {"status": "error", "reason": reason}

    try:
        background_tasks.add_task(service.upsert_reservation, payload)
        return {"status": "success", "message": "Reservation data is being processed."}
    except Exception as e:
        discord.error(title="Webhook Processing Error", description=str(e))
        logger.error(f"Error processing webhook: {e}")
        return {"status": "error", "reason": str(e)}
    
app.include_router(router)