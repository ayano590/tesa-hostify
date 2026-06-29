from database import Database

db = Database()

rows = db.list_active_reservations()

for row in rows:
    print(dict(row))

db.close()