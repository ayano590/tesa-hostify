from tenacity import retry, stop_after_attempt, wait_exponential
from app.ttlock_client import TTLockClient
from app.tesa_client import TESAClient
import logging
import time
from app.monitoring import DiscordNotifier

logger = logging.getLogger("sync")
discord = DiscordNotifier()

PIN_KEYS = ["pin1", "pin2", "pin3", "pin4", "pin5", "pin6", "pin7"]
ROOM_TO_PIN = {
        "1": "pin2",
        "2": "pin6",
        "3": "pin3",
        "4": "pin4",
        "5": "pin5",
        "6": "pin7",
    }

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def _execute_tesa_sync(tesa, new_pins):
    logger.info("Logging into TESA...")
    tesa.login()
    logger.info("Login successful.")

    current_pins = tesa.get_common_pins()["commonPinsInfo"]
    
    if all(current_pins.get(pin) == value for pin, value in new_pins.items()):
        logger.info("No changes to sync with TESA.")
    else:
        logger.info("Updating pins...")
        current_pins.update(new_pins)
        tesa.update_common_pins(current_pins)
        logger.info("TESA update submitted.")
        time.sleep(15)

    actual_pins = tesa.get_common_pins()["commonPinsInfo"]
    failed_pins = [
        pin_name
        for pin_name, value in new_pins.items()
        if actual_pins.get(pin_name) != value
    ]
    if failed_pins:
        logger.error("TESA read-back mismatch for %d pin(s).", len(failed_pins))
        failed_rooms = [
            room_number
            for room_number, pin_name in ROOM_TO_PIN.items()
            if pin_name in failed_pins
        ]
        return {
            "status": "error",
            "failed_rooms": failed_rooms,
        }
    return {"status": "success"}


def sync_to_tesa(active_reservations):
    logger.info(f"Syncing to TESA...")

    new_pins = {
        pin: r["door_code"]
        for r in active_reservations
        if (pin := ROOM_TO_PIN.get(r["room_number"])) is not None
    }

    tesa = TESAClient()

    try:
        result = _execute_tesa_sync(tesa, new_pins)
        if result["status"] == "error":
            discord.error(
                title="Tesa sync error",
                description="Door code update was not verified for these rooms.",
                fields=[{"name": "Room Numbers", "value": ", ".join(result["failed_rooms"])}],
            )
        return result
    except Exception as e:
        failed_rooms = [
            r["room_number"]
            for r in active_reservations
            if r["room_number"] in ROOM_TO_PIN
        ]
        discord.error(
            title="Tesa sync error",
            description=str(e),
            fields=[{"name": "Room Numbers", "value": ", ".join(failed_rooms)}],
        )
        logger.error(f"Error occurred while syncing to TESA after retries: {e}")
        return {"status": "error", "stage": "sync_failed"}
    finally:
        try:
            tesa.close()
            logger.info("TESA client closed.")
        except Exception as e:
            discord.warning(title="Tesa Close error", description=str(e))
            logger.warning("Error occurred while closing TESA client.")



@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def _retry_ttlock_update(ttlock, access_token, room_number, door_code):
    logger.info(f"Updating door code for room {room_number}...")
    ttlock.update_door_code(access_token, room_number, door_code)


def sync_to_ttlock(active_reservations):
    logger.info(f"Syncing to TTLock...")

    ttlock = TTLockClient()
    error_rooms = set()

    try:
        logger.info("Getting access token from TTLock...")
        access_token = ttlock.get_access_token()
        
        for r in active_reservations:
            room_number = r["room_number"]

            if room_number not in ["2", "6"]:
                logger.info(f"Skipping room {room_number}...")
                continue

            door_code = r["door_code"]
            
            try:
                current_code = ttlock.get_door_code(access_token, room_number)
                if str(current_code or "") == str(door_code or ""):
                    logger.info(f"Room {room_number} already has the requested TTLock code.")
                else:
                    _retry_ttlock_update(ttlock, access_token, room_number, door_code)
                    time.sleep(15)
                    actual_code = ttlock.get_door_code(access_token, room_number)
                    if str(actual_code or "") != str(door_code or ""):
                        raise ValueError("TTLock code read-back did not match the requested code")
            except Exception as e:
                error_rooms.add(room_number)
                discord.error(
                    title="TTLock sync error",
                    description=str(e),
                    fields=[{"name": "Room Number", "value": room_number}],
                )
                logger.error(f"Failed to update room {room_number} after multiple retries: {e}")
                continue 

        logger.info("TTLock update batch completed.")
        status = "error" if error_rooms else "success"
        return {"status": status}

    except Exception as e:
        failed_rooms = [
            r["room_number"]
            for r in active_reservations
            if r["room_number"] in ["2", "6"]
        ]
        discord.error(
            title="TTLock critical error",
            description=str(e),
            fields=[{"name": "Room Numbers", "value": ", ".join(failed_rooms)}],
        )
        logger.error(f"Critical error occurred while syncing to TTLock: {e}")
        return {"status": "error", "stage": "sync"}
    finally:
        try:
            ttlock.close()
            logger.info("TTLock client closed.")
        except Exception as e:
            discord.warning(title="TTLock Close error", description=str(e))
            logger.warning("Error occurred while closing TTLock client.")


def read_current_ttlock_door_codes():
    rooms = ("2", "6")
    locks = []
    errors = []
    ttlock = TTLockClient()

    try:
        access_token = ttlock.get_access_token()
        if not access_token:
            raise ValueError("TTLock did not return an access token.")
    except Exception as e:
        logger.error("Failed to read TTLock door codes: %s", e)
        errors.extend(
            {
                "provider": "TTLOCK",
                "room_number": room_number,
                "error_code": "authentication_failed",
            }
            for room_number in rooms
        )
    else:
        for room_number in rooms:
            try:
                door_code = ttlock.get_door_code(access_token, room_number)
                locks.append({
                    "room_number": room_number,
                    "provider": "TTLOCK",
                    "door_code": str(door_code or ""),
                })
            except Exception as e:
                logger.error(
                    "Failed to read TTLock code for room %s: %s",
                    room_number,
                    e,
                )
                errors.append({
                    "provider": "TTLOCK",
                    "room_number": room_number,
                    "error_code": "read_failed",
                })
    finally:
        try:
            ttlock.close()
        except Exception as e:
            logger.warning("Failed to close TTLock client after reading codes: %s", e)

    return {"locks": locks, "provider_errors": errors}


def read_current_tesa_pins():
    locks = []
    errors = []
    tesa = TESAClient()

    try:
        tesa.login()
        response = tesa.get_common_pins()
        if not isinstance(response, dict) or not isinstance(response.get("commonPinsInfo"), dict):
            raise ValueError("TESA common-pin response is missing commonPinsInfo.")

        pins = response["commonPinsInfo"]
        for room_number, pin_name in ROOM_TO_PIN.items():
            locks.append({
                "room_number": room_number,
                "provider": "TESA",
                "door_code": str(pins.get(pin_name) or ""),
            })
    except Exception as e:
        logger.error("Failed to read TESA door pins: %s", e)
        errors.append({
            "provider": "TESA",
            "error_code": "read_failed",
        })
    finally:
        try:
            tesa.close()
        except Exception as e:
            logger.warning("Failed to close TESA client after reading pins: %s", e)

    return {"locks": locks, "provider_errors": errors}
