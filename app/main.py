from database import Database

db = Database()

db.update_reservation_fields("12345", {
    "door_code": "5678",
    "status": "active"
})
print(dict(db.get_reservation_by_hostify_id("12345")))

db.close()