from database import Database

db = Database()
row = db.get_reservation_by_hostify_id("12345")
print("Retrieved reservation:", dict(row) if row else "No reservation found.")
db.close()