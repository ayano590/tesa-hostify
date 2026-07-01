import datetime
from code_generator import generate_door_code
import logging

logger = logging.getLogger("reservation")

class ReservationService:
    def __init__(self, db, sync_to_tesa):
        self.db = db
        self.sync = sync_to_tesa

    def upsert_reservation(self, payload):
        hostify_id = payload["hostify_id"]
        room_number = payload["room_number"]
        door_code = generate_door_code(room_number, hostify_id)

        data = {
            "hostify_id": hostify_id,
            "guest_name": payload["guest_name"],
            "room_number": room_number,
            "door_code": door_code,
            "arrival": payload["arrival"],
            "departure": payload["departure"],
            "status": payload["status"]
        }

        logger.info(f"Upsert reservation {payload["hostify_id"]} status={payload["status"]}")
        self.db.upsert_reservation(data)

    def delete_old_reservations(self):
        logger.info("Deleting old reservations...")
        self.db.delete_old_reservations()

    def process_status_changes(self):
        reservations = self.db.list_all_reservations()
        now = datetime.now()

        for r in reservations:
            new_status = self._compute_status(r, now)

            if r["status"] != new_status:
                logger.info(f"Updating reservation {r["hostify_id"]} status to {new_status}.")
                self.db.update_reservation_status(r["hostify_id"], new_status)
                self.sync.sync_to_tesa(r["status"], r["room_number"], r["door_code"])

    def _compute_status(self, r, now):
        arrival = datetime.fromisoformat(r["arrival"])
        departure = datetime.fromisoformat(r["departure"])

        if r["status"] == "cancelled":
            return "cancelled"

        if now < arrival:
            return "confirmed"
        
        if arrival <= now <= departure:
            return "active"
        
        if now > departure:
            return "completed"
        
        return r["status"]