from tesa_client import TESAClient
import logging

logger = logging.getLogger("tesa")

PIN_KEYS = ["pin1", "pin2", "pin3", "pin4", "pin5"]

def sync_to_tesa(status, room_number, door_code):
    
    if status != "active":
        logger.info("Reservation is not active, skipping sync.")
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

        pin = map_room_to_pin(room_number)

        if not pin:
            logger.info(f"Ignored room number {room_number}")
            return {"status": "no_changes"}
        
        logger.info(f"Updating pin={pin}")

        current[pin] = door_code

        payload = {k: current.get(k, "") for k in PIN_KEYS}

        result = tesa.update_common_pins(payload)

        logger.info(f"TESA update success pin={pin}")

        return {"status": "updated", "result": result}

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
        "3": "pin3",
        "4": "pin4",
        "5": "pin5",
    }.get(str(room_number))
