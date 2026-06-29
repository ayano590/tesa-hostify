from dotenv import load_dotenv
import os
from database import Database

load_dotenv()

MAIN_ENTRANCE_PIN = os.getenv("MAIN_ENTRANCE_PIN")
PIN_KEYS = ["pin1", "pin2", "pin3", "pin4", "pin5"]

def build_state_from_db(db):
    reservations = db.list_active_reservations()

    state = {
        "pin1": MAIN_ENTRANCE_PIN,  # konstant
        "pin2": "",
        "pin3": "",
        "pin4": "",
        "pin5": "",
    }

    for r in reservations:
        room = str(r["room_number"])
        code = r["door_code"]

        if room == "1":
            state["pin2"] = code
        elif room == "3":
            state["pin3"] = code
        elif room == "4":
            state["pin4"] = code
        elif room == "5":
            state["pin5"] = code

    return state

def build_patch(current, desired):
    patch = {}

    for k in PIN_KEYS:
        if current.get(k) != desired.get(k):
            patch[k] = desired.get(k)

    return patch

def sync_to_tesa(pms):
    db = Database()

    # 1. current state aus TESA
    current = pms.get_common_pins()["commonPinsInfo"]

    # 2. desired state aus DB
    desired = build_state_from_db(db)

    # 3. diff berechnen
    patch = build_patch(current, desired)

    # 4. nichts zu tun
    if not patch:
        return {"status": "no_changes"}

    # 5. safe merge (KEIN full overwrite blind)
    updated = current.copy()
    updated.update(patch)

    # 6. push to TESA
    result = pms.update_common_pins(updated)

    return {
        "status": "updated",
        "patch": patch,
        "result": result
    }