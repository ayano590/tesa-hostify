from database import Database

db = Database()

db.delete_reservation("12345")

row = db.get_reservation_by_hostify_id("12345")

print(row)  # This should print None if the reservation was successfully deleted

db.close()