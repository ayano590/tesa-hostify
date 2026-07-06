from ttlock_client import TTLockClient
from tesa_client import TESAClient
import logging

logger = logging.getLogger("sync")

PIN_KEYS = ["pin1", "pin2", "pin3", "pin4", "pin5", "pin6", "pin7"]

def sync_to_tesa(room_number, door_code):
    logger.info(f"Syncing to TESA...")

    pin = map_room_to_pin(room_number)

    if not pin:
        logger.info(f"Ignored room number {room_number}")
        return {"status": "no_changes"}

    tesa = TESAClient()

    try:
        logger.info("Logging into TESA...")
        tesa.login()
        logger.info("Login successful.")
    except Exception as e:
        logger.error(f"Error occurred while logging into TESA: {e}")
        return {"status": "error", "stage": "login"}

    try:
        current = tesa.get_common_pins()["commonPinsInfo"]
        
        if current[pin] == door_code:
            logger.info("Door code is already up to date, no changes needed.")
            return {"status": "no_changes"}
        
        logger.info(f"Updating {pin}...")
        current[pin] = door_code
        payload = {k: current.get(k, "") for k in PIN_KEYS}
        tesa.update_common_pins(payload)
        logger.info(f"TESA update success {pin}")
        return {"status": "success"}

    except Exception as e:
        logger.error(f"Error occurred while syncing to TESA: {e}")
        return {"status": "error", "stage": "sync"}

    finally:
        try:
            tesa.close()
            logger.info("TESA client closed.")
        except Exception:
            logger.warning("Error occurred while closing TESA client.")

def map_room_to_pin(room_number):
    return {
        "1": "pin2",
        "2": "pin6",
        "3": "pin3",
        "4": "pin4",
        "5": "pin5",
        "6": "pin7",
    }.get(str(room_number))

def sync_to_ttlock(room_number, door_code):
    logger.info(f"Syncing to TTLock...")

    if room_number not in ["2", "6"]:
        logger.info(f"Ignored room number {room_number}")
        return {"status": "no_changes"}

    ttlock = TTLockClient()

    try:
        logger.info("Getting access token from TTLock...")
        access_token = ttlock.get_access_token()
        logger.info(f"Updating door code for room {room_number}...")
        ttlock.update_door_code(access_token, room_number, door_code)
        logger.info(f"TTLock update success for room {room_number}")
        return {"status": "success"}

    except Exception as e:
        logger.error(f"Error occurred while syncing to TTLock: {e}")
        return {"status": "error", "stage": "sync"}

    finally:
        try:
            ttlock.close()
            logger.info("TTLock client closed.")
        except Exception:
            logger.warning("Error occurred while closing TTLock client.")