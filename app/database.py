from pathlib import Path
import sqlite3

DB_PATH = Path("hotel.db")


class Database:
    def __init__(self):
        self.init_db()

    def _get_connection(self):
        conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level="IMMEDIATE")
        conn.row_factory = sqlite3.Row

        conn.execute("PRAGMA foreign_keys=ON;")

        return conn

    def init_db(self):
        try:
            with self._get_connection() as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS reservations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        reservation_id TEXT UNIQUE,
                        guest_name TEXT,
                        room_number TEXT,
                        door_code TEXT,
                        check_in TIMESTAMP,
                        check_out TIMESTAMP,
                        status TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to initialize database: {e}") from e

    def upsert_reservation(self, data: dict):
        try:
            with self._get_connection() as conn:

                conn.execute("""
                    INSERT INTO reservations (
                        reservation_id,
                        guest_name,
                        room_number,
                        door_code,
                        check_in,
                        check_out,
                        status,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?,
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    )
                    ON CONFLICT(reservation_id)
                    DO UPDATE SET
                        guest_name = excluded.guest_name,
                        room_number = excluded.room_number,
                        door_code = excluded.door_code,
                        check_in = excluded.check_in,
                        check_out = excluded.check_out,
                        status = excluded.status,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    data["reservation_id"],
                    data["guest_name"],
                    data["room_number"],
                    data["door_code"],
                    data["check_in"],
                    data["check_out"],
                    data["status"],
                ))

        except sqlite3.Error as e:
            raise RuntimeError(
                f"Failed to upsert reservation '{data['reservation_id']}': {e}"
            ) from e

    def update_reservation_status(self, reservation_id: str, status: str) -> int:
        try:
            with self._get_connection() as conn:

                cursor = conn.execute("""
                    UPDATE reservations
                    SET
                        status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE reservation_id = ?
                """, (status, reservation_id))

                return cursor.rowcount

        except sqlite3.Error as e:
            raise RuntimeError(
                f"Failed to update reservation '{reservation_id}' to status '{status}': {e}"
            ) from e

    def delete_old_reservations(self):
        try:
            with self._get_connection() as conn:

                conn.execute("""
                    DELETE FROM reservations
                    WHERE check_out < datetime('now', '-30 days')
                """)

        except sqlite3.Error as e:
            raise RuntimeError(
                f"Failed to delete old reservations: {e}"
            ) from e

    def list_all_reservations(self):
        try:
            with self._get_connection() as conn:
                rows = conn.execute("""
                    SELECT *
                    FROM reservations
                    ORDER BY check_in
                """).fetchall()

                return [dict(row) for row in rows]

        except sqlite3.Error as e:
            raise RuntimeError(
                f"Failed to list reservations: {e}"
            ) from e

    def get_reservation(self, reservation_id: str):
        try:
            with self._get_connection() as conn:
                row = conn.execute("""
                    SELECT *
                    FROM reservations
                    WHERE reservation_id = ?
                """, (reservation_id,)).fetchone()

                return dict(row) if row else None

        except sqlite3.Error as e:
            raise RuntimeError(
                f"Failed to fetch reservation '{reservation_id}': {e}"
            ) from e
        
    def truncate_WAL(self):
        try:
            with self._get_connection() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")

        except sqlite3.Error as e:
            raise RuntimeError(
                f"Failed to truncate WAL: {e}"
            ) from e