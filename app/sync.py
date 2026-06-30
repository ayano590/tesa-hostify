from tesa_client import TESAClient

PIN_KEYS = ["pin1", "pin2", "pin3", "pin4", "pin5"]

def sync_to_tesa(status, room_number, door_code):
    
    if status != "active":
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

        current[pin] = door_code

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
        except Exception:
            pass

def map_room_to_pin(room_number):
    return {
        "1": "pin2",
        "3": "pin3",
        "4": "pin4",
        "5": "pin5",
    }.get(str(room_number))
