import sqlite3
from pathlib import Path

DB_PATH = Path("hotel.db")

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def init_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reservation_id TEXT UNIQUE,
                guest_name TEXT,
                room_number TEXT,
                door_code TEXT,
                checkIn TIMESTAMP,
                checkOut TIMESTAMP,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def upsert_reservation(self, data):
        self.cursor.execute('''
            INSERT INTO reservations (
                            reservation_id,
                            guest_name,
                            room_number,
                            door_code,
                            checkIn,
                            checkOut,
                            status,
                            created_at,
                            updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(reservation_id) DO UPDATE SET
                guest_name=excluded.guest_name,
                room_number=excluded.room_number,
                door_code=excluded.door_code,
                checkIn=excluded.checkIn,
                checkOut=excluded.checkOut,
                status=excluded.status,
                updated_at=excluded.updated_at
        ''', (
            data["reservation_id"],
            data["guest_name"],
            data["room_number"],
            data["door_code"],
            data["checkIn"],
            data["checkOut"],
            data["status"]
        ))

        self.conn.commit()

    # def get_reservation_by_reservation_id(self, reservation_id):
    #     self.cursor.execute('''
    #         SELECT * FROM reservations WHERE reservation_id = ?
    #     ''', (reservation_id,))
    #     return self.cursor.fetchone()
    
    def update_reservation_status(self, reservation_id, status):
        self.cursor.execute('''
            UPDATE reservations SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE reservation_id = ?
        ''', (status, reservation_id))
        self.conn.commit()
        return self.cursor.rowcount

    def delete_old_reservations(self):
        self.cursor.execute('''
            DELETE FROM reservations WHERE checkOut < datetime('now', '-30 days')
        ''')
        self.conn.commit()

    def list_all_reservations(self):
        self.cursor.execute('''
            SELECT * FROM reservations
        ''')
        return self.cursor.fetchall()

    def close(self):
        self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        self.conn.close()