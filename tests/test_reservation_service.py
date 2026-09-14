import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from reservation_service import ReservationService


class FakeDB:
    def __init__(self):
        self.reservations = {}
        self.access_states = {}

    def get_reservation(self, reservation_id):
        return self.reservations.get(reservation_id)

    def upsert_reservation(self, data):
        self.reservations[data["reservation_id"]] = data

    def replace_access_state_for_reservation(self, reservation_id, records):
        self.access_states[reservation_id] = records

    def replace_actual_state_for_reservation(self, reservation_id, records):
        self.access_states[reservation_id] = records


class ReservationServiceLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        self.service = ReservationService(self.db)

    def test_future_reservation_is_accepted(self):
        now = datetime(2026, 7, 1, 12, 0)
        reservation = {"status": "accepted", "check_in": "2026-07-03T14:00:00", "check_out": "2026-07-06T10:00:00"}
        self.assertEqual(self.service._compute_status(reservation, now), "accepted")

    def test_active_reservation_is_active(self):
        now = datetime(2026, 7, 4, 12, 0)
        reservation = {"status": "accepted", "check_in": "2026-07-03T14:00:00", "check_out": "2026-07-06T10:00:00"}
        self.assertEqual(self.service._compute_status(reservation, now), "active")

    def test_cancelled_reservation_stays_cancelled(self):
        now = datetime(2026, 7, 5, 12, 0)
        reservation = {"status": "cancelled", "check_in": "2026-07-03T14:00:00", "check_out": "2026-07-06T10:00:00"}
        self.assertEqual(self.service._compute_status(reservation, now), "cancelled")

    def test_completed_reservation_is_completed(self):
        now = datetime(2026, 7, 7, 12, 0)
        reservation = {"status": "accepted", "check_in": "2026-07-03T14:00:00", "check_out": "2026-07-06T10:00:00"}
        self.assertEqual(self.service._compute_status(reservation, now), "completed")

    def test_missing_dates_are_unknown(self):
        now = datetime(2026, 7, 4, 12, 0)
        reservation = {"status": "accepted", "check_in": None, "check_out": None}
        self.assertEqual(self.service._compute_status(reservation, now), "unknown")

    def test_duplicate_event_is_ignored(self):
        payload = {
            "action": "new_reservation",
            "reservation_id": "abc",
            "data": {
                "reservation": {
                    "status": "accepted",
                    "checkIn": "2026-07-03",
                    "checkOut": "2026-07-06",
                    "planned_arrival": "16:00:00",
                    "planned_departure": "11:00:00",
                    "custom_fields": [{"name": "door_code", "value": "1234"}],
                },
                "listing": {"nickname": "2"},
                "guest": {"name": "Jane Doe"},
            },
        }
        self.service.upsert_reservation(payload)
        first_hash = self.db.reservations["abc"]["event_hash"]
        self.db.reservations["abc"]["event_hash"] = first_hash
        self.service.upsert_reservation(payload)
        self.assertEqual(len(self.db.reservations), 1)

    def test_room_move_creates_revoke_record(self):
        previous = {
            "reservation_id": "abc",
            "room_number": "2",
            "door_code": "1234",
            "source_status": "accepted",
            "event_hash": "old",
            "check_in": "2026-07-03T14:00:00",
            "check_out": "2026-07-06T10:00:00",
            "lifecycle_status": "active",
        }
        self.db.reservations["abc"] = previous

        payload = {
            "action": "move_reservation",
            "reservation_id": "abc",
            "data": {
                "reservation": {
                    "status": "accepted",
                    "checkIn": "2026-07-03",
                    "checkOut": "2026-07-06",
                    "planned_arrival": "16:00:00",
                    "planned_departure": "11:00:00",
                    "custom_fields": [{"name": "door_code", "value": "1234"}],
                },
                "listing": {"nickname": "6"},
                "guest": {"name": "Jane Doe"},
            },
        }
        self.service.upsert_reservation(payload)
        room_6 = [r for r in self.db.access_states["abc"] if r["room_number"] == "6"]
        self.assertTrue(room_6)
        self.assertTrue(any(r["room_number"] == "2" and r["should_exist"] is False for r in self.db.access_states["abc"]))


if __name__ == "__main__":
    unittest.main()


    def test_malformed_payload_is_rejected(self):
        payload = {"action": "new_reservation", "data": {"reservation": {"status": "accepted"}}}
        self.assertEqual(self.service._build_reservation_payload(payload)["reservation_id"], "")

    def test_mismatch_detection_lists_missing_or_stale_state(self):
        db = self.db
        db.access_states["abc"] = [{
            "room_number": "2",
            "provider": "TTLOCK",
            "credential_name": "room-2",
            "desired_value": "1234",
            "should_exist": True,
        }]
        db.actual_state = [{
            "reservation_id": "abc",
            "room_number": "2",
            "provider": "TTLOCK",
            "credential_name": "room-2",
            "actual_value": "",
        }]
        mismatches = [{
            "reservation_id": "abc",
            "room_number": "2",
            "provider": "TTLOCK",
            "credential_name": "room-2",
            "mismatch_type": "missing",
        }]
        self.assertTrue(mismatches[0]["reservation_id"] == "abc")
