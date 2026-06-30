import datetime

class ReservationService:
    def __init__(self, db, sync_to_tesa):
        self.db = db
        self.sync = sync_to_tesa

    def process_status_changes(self):
        reservations = self.db.list_all_reservations()
        now = datetime.now()

        for r in reservations:
            new_status = self._compute_status(r, now)

            if r["status"] != new_status:
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