import logging
import time
from contextlib import ExitStack

from tenacity import retry, stop_after_attempt, wait_exponential

from .monitoring import DiscordNotifier
from .tesa_client import TESAClient
from .ttlock_client import TTLockClient

logger = logging.getLogger("sync")
discord = DiscordNotifier()

PIN_KEYS = ["pin1", "pin2", "pin3", "pin4", "pin5", "pin6", "pin7"]
ROOM_TO_PIN = {"1": "pin2", "2": "pin6", "3": "pin3", "4": "pin4", "5": "pin5", "6": "pin7"}


def normalize_pin_value(value):
    if value is None:
        return ""
    value = str(value).strip()
    return value if value else ""


def read_current_lock_codes():
    with ExitStack() as stack:
        tesa = TESAClient()
        stack.callback(tesa.close)
        ttlock = TTLockClient()
        stack.callback(ttlock.close)

        tesa.login()
        tesa_response = tesa.get_common_pins()
        if not isinstance(tesa_response, dict) or not isinstance(tesa_response.get("commonPinsInfo"), dict):
            raise ValueError("TESA common-pin response is missing commonPinsInfo")
        common_pins = tesa_response["commonPinsInfo"]

        lock_codes = [
            {
                "room_number": room_number,
                "provider": "TESA",
                "door_code": normalize_pin_value(common_pins.get(pin_name)),
            }
            for room_number, pin_name in ROOM_TO_PIN.items()
        ]

        access_token = ttlock.get_access_token()
        lock_codes.extend(
            {
                "room_number": room_number,
                "provider": "TTLOCK",
                "door_code": normalize_pin_value(
                    ttlock.get_door_code(access_token, room_number)
                ),
            }
            for room_number in ("2", "6")
        )

        return lock_codes


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _execute_tesa_sync(tesa, desired_pins):
    logger.info("Logging into TESA...")
    tesa.login()
    logger.info("Login successful.")

    current_response = tesa.get_common_pins()
    if not isinstance(current_response, dict) or not isinstance(current_response.get("commonPinsInfo"), dict):
        raise ValueError("TESA common-pin read-back response is missing commonPinsInfo")
    current_pins = current_response["commonPinsInfo"]
    current_map = {str(k).lower(): normalize_pin_value(v) for k, v in current_pins.items() if str(k).lower().startswith("pin")}
    normalized_target = {str(k).lower(): normalize_pin_value(v) for k, v in desired_pins.items() if str(k).lower().startswith("pin")}

    if all(current_map.get(pin, "") == value for pin, value in normalized_target.items()):
        logger.info("No changes to sync with TESA.")
        observed_pins = current_map
        status = "no_changes"
    else:
        merged = dict(current_pins)
        merged.update(normalized_target)
        tesa.update_common_pins(merged)
        readback = tesa.get_common_pins()
        if not isinstance(readback, dict) or not isinstance(readback.get("commonPinsInfo"), dict):
            raise ValueError("TESA common-pin read-back response is missing commonPinsInfo")
        observed_pins = {
            str(k).lower(): normalize_pin_value(v)
            for k, v in readback["commonPinsInfo"].items()
            if str(k).lower().startswith("pin")
        }
        status = "success"

    failed_pins = [
        pin for pin, desired_value in normalized_target.items()
        if observed_pins.get(pin, "") != desired_value
    ]
    if failed_pins:
        logger.error("TESA read-back mismatch on %d pin(s).", len(failed_pins))
        status = "error"
    return {"status": status, "actual_pins": observed_pins, "failed_pins": failed_pins}


def sync_to_tesa(desired_access):
    desired_pins = {}
    for item in desired_access or []:
        if item.get("provider") != "TESA":
            continue
        room_number = str(item.get("room_number", ""))
        pin_name = ROOM_TO_PIN.get(room_number)
        if pin_name is None:
            continue
        desired_pins[pin_name] = normalize_pin_value(item.get("desired_value", ""))

    logger.info("Syncing %d TESA pin entries.", len(desired_pins))
    tesa = TESAClient()

    try:
        result = _execute_tesa_sync(tesa, desired_pins)
        result["actual_state"] = [
            {
                "room_number": str(item.get("room_number", "")),
                "provider": "TESA",
                "credential_name": ROOM_TO_PIN[str(item.get("room_number", ""))],
                "actual_value": result["actual_pins"].get(
                    ROOM_TO_PIN[str(item.get("room_number", ""))],
                    "",
                ),
            }
            for item in desired_access or []
            if item.get("provider") == "TESA"
            and str(item.get("room_number", "")) in ROOM_TO_PIN
        ]
        result["failed_rooms"] = [
            str(item.get("room_number", ""))
            for item in desired_access or []
            if item.get("provider") == "TESA"
            and ROOM_TO_PIN.get(str(item.get("room_number", ""))) in result.get("failed_pins", [])
        ]
        if result["failed_rooms"]:
            discord.error(
                title="TESA read-back mismatch",
                description="TESA returned a credential value different from the requested state.",
                fields=[{"name": "Rooms", "value": ", ".join(sorted(set(result["failed_rooms"])))}],
            )
        return result
    except Exception as error:
        failed_rooms = [
            str(item.get("room_number", ""))
            for item in desired_access or []
            if item.get("provider") == "TESA"
            and str(item.get("room_number", "")) in ROOM_TO_PIN
        ]
        discord.error(
            title="TESA synchronization failed",
            description="TESA update or read-back failed; reconciliation will retry.",
            fields=[
                {"name": "Rooms", "value": ", ".join(sorted(set(failed_rooms))) or "unknown"},
                {"name": "Error Type", "value": type(error).__name__},
            ],
        )
        logger.error("Error occurred while syncing to TESA (%s).", type(error).__name__)
        return {"status": "error", "stage": "sync_failed", "failed_rooms": failed_rooms}
    finally:
        try:
            tesa.close()
            logger.info("TESA client closed.")
        except Exception as error:
            logger.warning("Error occurred while closing TESA client (%s).", type(error).__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _retry_ttlock_update(ttlock, access_token, room_number, door_code, remove=False):
    if remove:
        logger.info(f"Revoking door code for room {room_number}...")
        return ttlock.revoke_door_code(access_token, room_number)

    logger.info(f"Updating door code for room {room_number}...")
    return ttlock.update_door_code(access_token, room_number, door_code)


def _read_ttlock_door_code_with_retry(ttlock, access_token, room_number, expected_value):
    actual_value = ""
    for attempt in range(3):
        actual_value = normalize_pin_value(ttlock.get_door_code(access_token, room_number))
        if actual_value == normalize_pin_value(expected_value):
            return actual_value
        if attempt < 2:
            time.sleep(2 ** attempt)
    return actual_value


def sync_to_ttlock(desired_access):
    ttlock_items = [item for item in desired_access or [] if item.get("provider") == "TTLOCK"]
    logger.info("Syncing %d TTLock credential entries.", len(ttlock_items))
    ttlock = TTLockClient()
    failed_rooms = []
    actual_state = []
    error_rooms = set()

    try:
        logger.info("Getting access token from TTLock...")
        access_token = ttlock.get_access_token()

        for item in ttlock_items:
            if item.get("provider") != "TTLOCK":
                continue

            room_number = str(item.get("room_number", ""))
            if room_number not in ["2", "6"]:
                logger.info(f"Skipping room {room_number}...")
                continue

            desired_value = item.get("desired_value")
            remove = bool(item.get("should_exist") is False or desired_value in (None, ""))

            try:
                _retry_ttlock_update(ttlock, access_token, room_number, desired_value, remove=remove)
                actual_value = _read_ttlock_door_code_with_retry(
                    ttlock,
                    access_token,
                    room_number,
                    desired_value,
                )
                actual_state.append({
                    "room_number": room_number,
                    "provider": "TTLOCK",
                    "credential_name": item.get("credential_name", f"room-{room_number}"),
                    "actual_value": actual_value,
                })
                expected_value = normalize_pin_value(desired_value)
                if actual_value != expected_value:
                    logger.error("TTLock read-back mismatch for room %s.", room_number)
                    failed_rooms.append(room_number)
                    error_rooms.add(room_number)
            except Exception as error:
                error_rooms.add(room_number)
                logger.error(
                    "Failed to sync TTLock room %s (%s).",
                    room_number,
                    type(error).__name__,
                )
                failed_rooms.append(room_number)
                continue

        if error_rooms:
            discord.error(
                title="TTLock synchronization failed",
                description="One or more TTLock updates or read-backs failed; reconciliation will retry.",
                fields=[{"name": "Rooms", "value": ", ".join(sorted(error_rooms))}],
            )
        logger.info("TTLock update batch completed.")
        if failed_rooms:
            return {
                "status": "error",
                "stage": "partial_sync",
                "failed_rooms": sorted(set(failed_rooms)),
                "actual_state": actual_state,
            }
        return {"status": "success", "actual_state": actual_state}
    except Exception as error:
        failed_rooms = sorted({
            str(item.get("room_number", ""))
            for item in ttlock_items
            if str(item.get("room_number", "")) in {"2", "6"}
        })
        discord.error(
            title="TTLock authentication or batch failure",
            description="TTLock authentication or synchronization could not complete.",
            fields=[
                {"name": "Rooms", "value": ", ".join(failed_rooms) or "unknown"},
                {"name": "Error Type", "value": type(error).__name__},
            ],
        )
        logger.error("Critical TTLock synchronization error (%s).", type(error).__name__)
        return {"status": "error", "stage": "sync"}
    finally:
        try:
            ttlock.close()
            logger.info("TTLock client closed.")
        except Exception as error:
            logger.warning("Error occurred while closing TTLock client (%s).", type(error).__name__)
