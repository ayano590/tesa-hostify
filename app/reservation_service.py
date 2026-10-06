from datetime import datetime, timedelta
from app.sync import sync_to_tesa, sync_to_ttlock
import logging
from app.monitoring import DiscordNotifier

logger = logging.getLogger("reservation")
discord = DiscordNotifier()

CHECKIN_HOUR = 14  # 1 hour buffer for check-in time
CHECKOUT_HOUR = 10

class ReservationService:
    def __init__(self, db):
        self.db = db

    def upsert_reservation(self, payload):
        reservation_id = payload["reservation_id"]
        room_number = next(
            char
            for char in payload["data"]["listing"]["nickname"]
            if char.isdigit()
        )

        checkInStr = payload["data"]["reservation"]["checkIn"]
        planned_arrival = payload["data"]["reservation"]["planned_arrival"]
        if planned_arrival in ["None", None, ""]:
            checkIn = datetime.fromisoformat(
                f"{checkInStr}T{CHECKIN_HOUR}:00:00"
            )
        else:
            checkIn = datetime.fromisoformat(
                f"{checkInStr}T{planned_arrival}"
            ) - timedelta(hours=1)
        checkIn = min(
            checkIn,
            datetime.fromisoformat(f"{checkInStr}T{CHECKIN_HOUR}:00:00"),
        )

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
            "check_in": checkIn,
            "check_out": checkOut,
            "status": payload["data"]["reservation"]["status"]
        }

        try:
            logger.info(f"Upsert reservation {payload['reservation_id']} status={payload['data']['reservation']['status']}")
            self.db.upsert_reservation(data)
        except Exception as e:
            discord.error(title="Reservation Upsert Error", description=str(e), fields=[{"name": "Reservation ID", "value": reservation_id}, {"name": "Room Number", "value": room_number}])
            logger.error(f"Error upserting reservation: {e}")

    def delete_old_reservations(self):
        try:
            logger.info("Deleting old reservations...")
            self.db.delete_old_reservations()
        except Exception as e:
            discord.error(title="Delete Old Reservations Error", description=str(e))
            logger.error(f"Error deleting old reservations: {e}")

    def process_status_changes(self):
        try:
            logger.info("Processing reservation status changes...")
            reservations = self.db.list_all_reservations()
        except Exception as e:
            discord.error(title="List All Reservations Error", description=str(e))
            logger.error(f"Error listing all reservations: {e}")
            return

        now = datetime.now()

        active_reservations = []

        for r in reservations:
            new_status = self._compute_status(r, now)

            # Update the status in the database if it has changed
            if r["status"] != new_status:
                try:
                    logger.info(f"Updating reservation {r['reservation_id']} status to {new_status}.")
                    self.db.update_reservation_status(r["reservation_id"], new_status)

                except Exception as e:
                    discord.error(title="Update Reservation Error", description=str(e), fields=[{"name": "Reservation ID", "value": r["reservation_id"]}, {"name": "new status", "value": new_status}])
                    logger.error(f"Error updating reservation with reservation ID {r['reservation_id']} to status: {new_status}")

            # If the reservation is now active, add it to the list of active reservations
            if new_status == "active":
                r["status"] = "active"
                active_reservations.append(r)

        if active_reservations:
            logger.info(f"Syncing {len(active_reservations)} active reservations to TESA and TTLock...")
            sync_to_tesa(active_reservations)
            sync_to_ttlock(active_reservations)

    def _compute_status(self, r, now):
        checkIn = datetime.fromisoformat(r["check_in"])
        checkOut = datetime.fromisoformat(r["check_out"])

        if r["status"] == "cancelled":
            return "cancelled"

        if now < checkIn:
            return "accepted"
        
        if checkIn <= now <= checkOut:
            return "active"
        
        if now > checkOut:
            return "completed"
        
        return r["status"]
    
    def truncate_WAL(self):
        try:
            logger.info(f"Truncating WAL file...")
            self.db.truncate_WAL()

        except Exception as e:
            discord.error(title="Truncate WAL Error", description=str(e))
            logger.error("Error truncating WAL file")