from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from datetime import date

DB_PATH = Path(__file__).resolve().parent / "hotel.db"


class Database:
    def __init__(self):
        self.init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level="IMMEDIATE")
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON;")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self):
        try:
            with self._get_connection() as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS reservations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        reservation_id TEXT UNIQUE,
                        guest_name TEXT,
                        room_number TEXT,
                        door_code TEXT,
                        check_in TIMESTAMP,
                        check_out TIMESTAMP,
                        source_status TEXT,
                        lifecycle_status TEXT DEFAULT 'unknown',
                        event_hash TEXT,
                        desired_access_state TEXT DEFAULT 'unknown',
                        sync_state TEXT DEFAULT 'unknown',
                        sync_provider TEXT,
                        sync_last_attempted_at TIMESTAMP,
                        sync_last_success_at TIMESTAMP,
                        sync_error TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS access_state (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        reservation_id TEXT NOT NULL,
                        room_number TEXT,
                        provider TEXT NOT NULL,
                        credential_name TEXT NOT NULL,
                        desired_value TEXT,
                        should_exist INTEGER NOT NULL DEFAULT 0,
                        reason TEXT,
                        sync_state TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(reservation_id, room_number, provider, credential_name)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS actual_state (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        reservation_id TEXT NOT NULL,
                        room_number TEXT,
                        provider TEXT NOT NULL,
                        credential_name TEXT NOT NULL,
                        actual_value TEXT,
                        sync_state TEXT DEFAULT 'unknown',
                        last_attempted_at TIMESTAMP,
                        last_success_at TIMESTAMP,
                        last_error TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(reservation_id, room_number, provider, credential_name)
                    )
                    """
                )
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to initialize database: {e}") from e

    def upsert_reservation(self, data: dict):
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO reservations (
                        reservation_id,
                        guest_name,
                        room_number,
                        door_code,
                        check_in,
                        check_out,
                        source_status,
                        lifecycle_status,
                        event_hash,
                        desired_access_state,
                        sync_state,
                        sync_provider,
                        sync_last_attempted_at,
                        sync_last_success_at,
                        sync_error,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
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
                        source_status = excluded.source_status,
                        lifecycle_status = excluded.lifecycle_status,
                        event_hash = excluded.event_hash,
                        desired_access_state = excluded.desired_access_state,
                        sync_state = excluded.sync_state,
                        sync_provider = excluded.sync_provider,
                        sync_last_attempted_at = excluded.sync_last_attempted_at,
                        sync_last_success_at = excluded.sync_last_success_at,
                        sync_error = excluded.sync_error,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        data["reservation_id"],
                        data.get("guest_name"),
                        data.get("room_number"),
                        data.get("door_code"),
                        data.get("check_in"),
                        data.get("check_out"),
                        data.get("source_status"),
                        data.get("lifecycle_status", "unknown"),
                        data.get("event_hash"),
                        data.get("desired_access_state", "unknown"),
                        data.get("sync_state", "unknown"),
                        data.get("sync_provider"),
                        data.get("sync_last_attempted_at"),
                        data.get("sync_last_success_at"),
                        data.get("sync_error"),
                    ),
                )
        except sqlite3.Error as e:
            raise RuntimeError(
                f"Failed to upsert reservation '{data['reservation_id']}': {e}"
            ) from e

    def update_reservation_status(self, reservation_id: str, status: str) -> int:
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    UPDATE reservations
                    SET source_status = ?,
                        lifecycle_status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE reservation_id = ?
                    """,
                    (status, status, reservation_id),
                )
                return cursor.rowcount
        except sqlite3.Error as e:
            raise RuntimeError(
                f"Failed to update reservation '{reservation_id}' to status '{status}': {e}"
            ) from e

    def update_lifecycle_status(self, reservation_id: str, lifecycle_status: str) -> int:
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    UPDATE reservations
                    SET lifecycle_status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE reservation_id = ?
                    """,
                    (lifecycle_status, reservation_id),
                )
                return cursor.rowcount
        except sqlite3.Error as e:
            raise RuntimeError(
                f"Failed to update reservation '{reservation_id}' lifecycle to '{lifecycle_status}': {e}"
            ) from e

    def update_sync_state(
        self,
        reservation_id: str,
        state: str,
        provider: str | None = None,
        desired_access_state: str | None = None,
        error: str | None = None,
    ) -> int:
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    UPDATE reservations
                    SET sync_state = ?,
                        sync_provider = COALESCE(?, sync_provider),
                        desired_access_state = COALESCE(?, desired_access_state),
                        sync_error = ?,
                        sync_last_attempted_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE reservation_id = ?
                    """,
                    (state, provider, desired_access_state, error, reservation_id),
                )
                return cursor.rowcount
        except sqlite3.Error as e:
            raise RuntimeError(
                f"Failed to update sync state for reservation '{reservation_id}': {e}"
            ) from e

    def mark_sync_success(self, reservation_id: str, provider: str | None = None, desired_access_state: str | None = None) -> int:
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    UPDATE reservations
                    SET sync_state = 'succeeded',
                        sync_provider = COALESCE(?, sync_provider),
                        desired_access_state = COALESCE(?, desired_access_state),
                        sync_last_success_at = CURRENT_TIMESTAMP,
                        sync_last_attempted_at = CURRENT_TIMESTAMP,
                        sync_error = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE reservation_id = ?
                    """,
                    (provider, desired_access_state, reservation_id),
                )
                return cursor.rowcount
        except sqlite3.Error as e:
            raise RuntimeError(
                f"Failed to mark sync success for reservation '{reservation_id}': {e}"
            ) from e

    def delete_old_reservations(self):
        try:
            with self._get_connection() as conn:
                expired_reservations = """
                    SELECT reservation_id
                    FROM reservations
                    WHERE check_out < datetime('now', '-30 days')
                """
                conn.execute(
                    f"""
                    DELETE FROM access_state
                    WHERE reservation_id IN ({expired_reservations})
                    """
                )
                conn.execute(
                    f"""
                    DELETE FROM actual_state
                    WHERE reservation_id IN ({expired_reservations})
                    """
                )
                conn.execute(
                    """
                    DELETE FROM reservations
                    WHERE check_out < datetime('now', '-30 days')
                    """
                )
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to delete old reservations: {e}") from e

    def list_all_reservations(self):
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM reservations
                    ORDER BY check_in
                    """
                ).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to list reservations: {e}") from e

    def list_reservations_checking_out_on_or_after(self, first_checkout_date: date):
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT reservation_id, room_number, check_in, check_out,
                           lifecycle_status, door_code
                    FROM reservations
                    WHERE date(check_out) >= ?
                    ORDER BY date(check_in), reservation_id
                    """,
                    (first_checkout_date.isoformat(),),
                ).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to list upcoming reservations: {e}") from e

    def get_reservation(self, reservation_id: str):
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT *
                    FROM reservations
                    WHERE reservation_id = ?
                    """,
                    (reservation_id,),
                ).fetchone()
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
            raise RuntimeError(f"Failed to truncate WAL: {e}") from e


    def get_event_hash(self, reservation_id: str):
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT event_hash
                    FROM reservations
                    WHERE reservation_id = ?
                    """,
                    (reservation_id,),
                ).fetchone()
                return row["event_hash"] if row else None
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to fetch event hash for '{reservation_id}': {e}") from e

    def replace_access_state_for_reservation(self, reservation_id: str, records):
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "DELETE FROM access_state WHERE reservation_id = ?",
                    (reservation_id,),
                )
                if not records:
                    return
                conn.executemany(
                    """
                    INSERT INTO access_state (
                        reservation_id,
                        room_number,
                        provider,
                        credential_name,
                        desired_value,
                        should_exist,
                        reason,
                        sync_state,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    [(
                        reservation_id,
                        record.get("room_number"),
                        record.get("provider"),
                        record.get("credential_name"),
                        record.get("desired_value"),
                        int(bool(record.get("should_exist"))),
                        record.get("reason"),
                    ) for record in records],
                )
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to replace access state for '{reservation_id}': {e}") from e

    def list_access_state(self):
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM access_state
                    ORDER BY reservation_id, provider, room_number
                    """
                ).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to list access state: {e}") from e

    def list_access_state_for_reservation(self, reservation_id: str):
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM access_state
                    WHERE reservation_id = ?
                    ORDER BY provider, room_number
                    """,
                    (reservation_id,),
                ).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            raise RuntimeError(
                f"Failed to list access state for '{reservation_id}': {e}"
            ) from e

    def replace_actual_state_for_reservation(self, reservation_id: str, records):
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "DELETE FROM actual_state WHERE reservation_id = ?",
                    (reservation_id,),
                )
                if not records:
                    return
                conn.executemany(
                    """
                    INSERT INTO actual_state (
                        reservation_id,
                        room_number,
                        provider,
                        credential_name,
                        actual_value,
                        sync_state,
                        last_attempted_at,
                        last_success_at,
                        last_error,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'unknown', CURRENT_TIMESTAMP, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    [(
                        reservation_id,
                        record.get("room_number"),
                        record.get("provider"),
                        record.get("credential_name"),
                        record.get("desired_value"),
                    ) for record in records],
                )
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to replace actual state for '{reservation_id}': {e}") from e

    def upsert_actual_state_for_reservation(self, reservation_id: str, records):
        try:
            with self._get_connection() as conn:
                conn.executemany(
                    """
                    INSERT INTO actual_state (
                        reservation_id,
                        room_number,
                        provider,
                        credential_name,
                        actual_value,
                        sync_state,
                        last_attempted_at,
                        last_success_at,
                        last_error,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'verified', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL,
                              CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT(reservation_id, room_number, provider, credential_name)
                    DO UPDATE SET
                        actual_value = excluded.actual_value,
                        sync_state = 'verified',
                        last_attempted_at = CURRENT_TIMESTAMP,
                        last_success_at = CURRENT_TIMESTAMP,
                        last_error = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    [(
                        reservation_id,
                        record.get("room_number"),
                        record.get("provider"),
                        record.get("credential_name"),
                        record.get("actual_value"),
                    ) for record in records],
                )
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to update actual state for '{reservation_id}': {e}") from e

    def list_actual_state(self):
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM actual_state
                    ORDER BY reservation_id, provider, room_number
                    """
                ).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to list actual state: {e}") from e


    def mark_sync_failed(self, reservation_id: str, provider: str | None = None, error: str | None = None) -> int:
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    UPDATE reservations
                    SET sync_state = 'failed',
                        sync_provider = COALESCE(?, sync_provider),
                        sync_error = ?,
                        sync_last_attempted_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE reservation_id = ?
                    """,
                    (provider, error, reservation_id),
                )
                return cursor.rowcount
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to mark sync failed for reservation '{reservation_id}': {e}") from e

    def list_mismatches(self):
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT a.reservation_id, a.room_number, a.provider, a.credential_name,
                           a.desired_value AS desired_value,
                           b.actual_value AS actual_value,
                           a.should_exist,
                           CASE
                               WHEN a.should_exist = 1 AND (b.actual_value IS NULL OR b.actual_value = '') THEN 'missing'
                               WHEN a.should_exist = 0 AND (b.actual_value IS NOT NULL AND b.actual_value != '') THEN 'stale'
                               WHEN a.desired_value IS NOT NULL AND b.actual_value IS NOT NULL AND a.desired_value != b.actual_value THEN 'value_mismatch'
                               ELSE 'match'
                           END AS mismatch_type
                    FROM access_state a
                    LEFT JOIN actual_state b
                      ON a.reservation_id = b.reservation_id
                     AND a.room_number = b.room_number
                     AND a.provider = b.provider
                     AND a.credential_name = b.credential_name
                    WHERE (
                        a.should_exist = 1
                        AND (
                            b.actual_value IS NULL
                            OR b.actual_value = ''
                            OR (a.desired_value IS NOT NULL AND a.desired_value != b.actual_value)
                        )
                    ) OR (
                        a.should_exist = 0
                        AND b.actual_value IS NOT NULL
                        AND b.actual_value != ''
                    )
                    ORDER BY a.reservation_id, a.provider, a.room_number
                    """
                ).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to list mismatches: {e}") from e
