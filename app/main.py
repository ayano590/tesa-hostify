from database import Database

db = Database()
db.init_db()

db.insert_reservation({
    "hostify_id": "12345",
    "guest_name": "John Doe",
    "room_number": "101",
    "door_code": "1234",
    "arrival": "2023-10-01 14:00:00",
    "departure": "2023-10-05 12:00:00",
    "status": "confirmed"
})

print("Reservation inserted successfully.")
db.close()