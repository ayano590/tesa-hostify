import datetime
from code_generator import generate_door_code
import logging

logger = logging.getLogger("reservation")

class ReservationService:
    def __init__(self, db, sync_to_tesa):
        self.db = db
        self.sync = sync_to_tesa

    def upsert_reservation(self, payload):
        reservation_id = payload["reservation_id"]
        room_number = payload["data"]["listing"]["nickname"]
        door_code = generate_door_code(room_number, reservation_id)

        data = {
            "reservation_id": reservation_id,
            "guest_name": payload["data"]["guest"]["name"],
            "room_number": room_number,
            "door_code": door_code,
            "arrival": payload["data"]["reservation"]["checkIn"],
            "departure": payload["data"]["reservation"]["checkOut"],
            "status": payload["data"]["reservation"]["status"]
        }

        logger.info(f"Upsert reservation {payload["reservation_id"]} status={payload["data"]["reservation"]["status"]}")
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
                logger.info(f"Updating reservation {r["reservation_id"]} status to {new_status}.")
                self.db.update_reservation_status(r["reservation_id"], new_status)
                self.sync.sync_to_tesa(r["status"], r["room_number"], r["door_code"])

    def _compute_status(self, r, now):
        arrival = datetime.fromisoformat(r["arrival"])
        departure = datetime.fromisoformat(r["departure"])

        if r["status"] == "cancelled":
            return "cancelled"

        if now < arrival:
            return "accepted"
        
        if arrival <= now <= departure:
            return "active"
        
        if now > departure:
            return "completed"
        
        return r["status"]