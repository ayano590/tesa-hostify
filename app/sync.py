from dotenv import load_dotenv
import os
from database import Database

load_dotenv()

MAIN_ENTRANCE_PIN = os.getenv("MAIN_ENTRANCE_PIN")
PIN_KEYS = ["pin1", "pin2", "pin3", "pin4", "pin5"]

class SyncService:
    def __init__(self, db, pms):
        self.db = db
        self.pms = pms

    def sync_to_tesa(self):
        # 1. current state aus TESA
        current = self.pms.get_common_pins()["commonPinsInfo"]

        # 2. desired state aus DB
        desired = self.build_state_from_db()

        # 3. diff
        patch = self.build_patch(current, desired)

        if not patch:
            return {"status": "no_changes"}

        updated = current.copy()
        updated.update(patch)

        result = self.pms.update_common_pins(updated)

        return {
            "status": "updated",
            "patch": patch,
            "result": result
        }

    def build_state_from_db(self):
        reservations = self.db.list_active_reservations()

        state = {
            "pin1": os.getenv("MAIN_ENTRANCE_PIN"),
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

    def build_patch(self, current, desired):
        patch = {}

        for k in PIN_KEYS:
            if current.get(k) != desired.get(k):
                patch[k] = desired.get(k)

        return patch