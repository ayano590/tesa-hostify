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

    def insert_reservation(self, data):
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
        ''', (
            data["hostify_id"],
            data["guest_name"],
            data["room_number"],
            data.get("door_code"),
            data["arrival"],
            data["departure"],
            data["status"]
        ))
        
        self.conn.commit()

    def close(self):
        self.conn.close()