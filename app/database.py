import sqlite3
from pathlib import Path

DB_PATH = Path("hotel.db")

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def init_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hostify_id TEXT UNIQUE,
                guest_name TEXT,
                room_number TEXT,
                door_code TEXT,
                arrival TIMESTAMP,
                departure TIMESTAMP,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def upsert_reservation(self, data):
        self.cursor.execute('''
            INSERT INTO reservations (
                            hostify_id,
                            guest_name,
                            room_number,
                            door_code,
                            arrival,
                            departure,
                            status,
                            created_at,
                            updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(hostify_id) DO UPDATE SET
                guest_name=excluded.guest_name,
                room_number=excluded.room_number,
                door_code=excluded.door_code,
                arrival=excluded.arrival,
                departure=excluded.departure,
                status=excluded.status,
                updated_at=excluded.updated_at
        ''', (
            data["hostify_id"],
            data["guest_name"],
            data["room_number"],
            data["door_code"],
            data["arrival"],
            data["departure"],
            data["status"]
        ))

        self.conn.commit()

    def get_reservation_by_hostify_id(self, hostify_id):
        self.cursor.execute('''
            SELECT * FROM reservations WHERE hostify_id = ?
        ''', (hostify_id,))
        return self.cursor.fetchone()
    
    def update_reservation_status(self, hostify_id, status):
        self.cursor.execute('''
            UPDATE reservations SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE hostify_id = ?
        ''', (status, hostify_id))
        self.conn.commit()
        return self.cursor.rowcount

    def delete_reservation(self, hostify_id):
        self.cursor.execute('''
            DELETE FROM reservations WHERE hostify_id = ?
        ''', (hostify_id,))
        self.conn.commit()

    def list_all_reservations(self):
        self.cursor.execute('''
            SELECT * FROM reservations
        ''')
        return self.cursor.fetchall()

    def close(self):
        self.conn.close()