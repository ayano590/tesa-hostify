from dotenv import load_dotenv
import os
from tesa_client import TESAClient

load_dotenv()

MAIN_ENTRANCE_PIN = os.getenv("MAIN_ENTRANCE_PIN")
PIN_KEYS = ["pin1", "pin2", "pin3", "pin4", "pin5"]

def sync_to_tesa(status, room_number, door_code):
    
    if status not in ("active", "completed"):
        return {"status": "no_changes"}

    tesa = TESAClient()

    try:
        tesa.login()
    except Exception as e:
        return {
            "status": "error",
            "stage": "login",
            "reason": str(e)
        }

    try:
        current = tesa.get_common_pins()["commonPinsInfo"]

        pin = map_room_to_pin(room_number)
        if not pin:
            return {"status": "error", "reason": "unknown_room"}

        current[pin] = door_code if status == "active" else ""

        payload = {k: current.get(k, "") for k in PIN_KEYS}

        result = tesa.update_common_pins(payload)

        return {"status": "updated", "result": result}

    except Exception as e:
        return {
            "status": "error",
            "stage": "sync",
            "reason": str(e)
        }

    finally:
        try:
            tesa.close()
        except:
            pass

def map_room_to_pin(room_number):
    return {
        "1": "pin2",
        "3": "pin3",
        "4": "pin4",
        "5": "pin5",
    }.get(str(room_number))
