from datetime import datetime
from sync import sync_to_tesa
import logging

logger = logging.getLogger("reservation")

CHECKIN_HOUR = 14  # 1 hour buffer for check-in time
CHECKOUT_HOUR = 10

class ReservationService:
    def __init__(self, db):
        self.db = db

    def upsert_reservation(self, payload):
        reservation_id = payload["reservation_id"]
        room_number = payload["data"]["listing"]["nickname"]

        checkInStr = payload["data"]["reservation"]["checkIn"]
        planned_arrival = payload["data"]["reservation"]["planned_arrival"]
        if planned_arrival in ["00:00:00", "None", None, ""]:
            planned_arrival = f"{CHECKIN_HOUR}:00:00"  # Default planned arrival time
        checkIn = datetime.fromisoformat(f"{checkInStr}T{planned_arrival}")

        checkOutStr = payload["data"]["reservation"]["checkOut"]
        planned_departure = payload["data"]["reservation"]["planned_departure"]
        if planned_departure in ["00:00:00", "None", None, ""]:
            planned_departure = f"{CHECKOUT_HOUR}:00:00"  # Default planned departure time
        checkOut = datetime.fromisoformat(f"{checkOutStr}T{planned_departure}")

        custom_fields = payload["data"]["reservation"]["custom_fields"]
        door_code = next((field["value"] for field in custom_fields if field["name"] == "door_code"), None)

        data = {
            "reservation_id": reservation_id,
            "guest_name": payload["data"]["guest"]["name"],
            "room_number": room_number,
            "door_code": door_code,
            "checkIn": checkIn,
            "checkOut": checkOut,
            "status": payload["data"]["reservation"]["status"]
        }

        logger.info(f"Upsert reservation {payload["reservation_id"]} status={payload["data"]["reservation"]["status"]}")
        self.db.upsert_reservation(data)

    def delete_old_reservations(self):
        logger.info("Deleting old reservations...")
        self.db.delete_old_reservations()

    def process_status_changes(self):
        logger.info("Processing reservation status changes...")
        reservations = self.db.list_all_reservations()
        now = datetime.now()

        for r in reservations:
            new_status = self._compute_status(r, now)

            if r["status"] != new_status:
                logger.info(f"Updating reservation {r["reservation_id"]} status to {new_status}.")
                self.db.update_reservation_status(r["reservation_id"], new_status)
                sync_to_tesa(r["status"], r["room_number"], r["door_code"])

    def _compute_status(self, r, now):
        checkIn = datetime.fromisoformat(r["checkIn"])
        checkOut = datetime.fromisoformat(r["checkOut"])

        if r["status"] == "cancelled":
            return "cancelled"

        if now < checkIn:
            return "accepted"
        
        if checkIn <= now <= checkOut:
            return "active"
        
        if now > checkOut:
            return "completed"
        
        return r["status"]
    
    def close(self):
        try:
            logger.info("Closing database connection...")
            self.db.close()
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")