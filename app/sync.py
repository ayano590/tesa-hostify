from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ttlock_client import TTLockClient
from tesa_client import TESAClient
import logging

logger = logging.getLogger("sync")

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
    
    if current_pins == new_pins:
        logger.info("No changes to sync with TESA.")
        return {"status": "no_changes"}
    
    logger.info(f"Updating pins...")
    current_pins.update(new_pins)
    tesa.update_common_pins(current_pins)
    logger.info(f"TESA update success.")
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
        return _execute_tesa_sync(tesa, new_pins)
    except Exception as e:
        logger.error(f"Error occurred while syncing to TESA after retries: {e}")
        return {"status": "error", "stage": "sync_failed"}
    finally:
        try:
            tesa.close()
            logger.info("TESA client closed.")
        except Exception:
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
                _retry_ttlock_update(ttlock, access_token, room_number, door_code)
            except Exception as e:
                logger.error(f"Failed to update room {room_number} after multiple retries: {e}")
                continue 

        logger.info("TTLock update batch completed.")
        return {"status": "success"}

    except Exception as e:
        logger.error(f"Critical error occurred while syncing to TTLock: {e}")
        return {"status": "error", "stage": "sync"}
    finally:
        try:
            ttlock.close()
            logger.info("TTLock client closed.")
        except Exception:
            logger.warning("Error occurred while closing TTLock client.")