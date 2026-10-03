import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from app import sync
from app.database import Database
from app.reservation_service import ReservationService
from app.ttlock_client import TTLockClient


class FakeTESAClient:
    initial_pins = {}
    instances = []

    def __init__(self):
        self.pins = dict(type(self).initial_pins)
        type(self).instances.append(self)

    def login(self):
        return {"status": "success"}

    def get_common_pins(self):
        return {"commonPinsInfo": dict(self.pins)}

    def update_common_pins(self, pins):
        self.pins.update(pins)
        return {"status": "success"}

    def close(self):
        pass


class FakeTTLockClient:
    credentials = {}
    observed_credentials = None
    instances = []

    def __init__(self):
        type(self).instances.append(self)

    def get_access_token(self):
        return "fake-token"

    def update_door_code(self, access_token, room_number, door_code):
        self.credentials[room_number] = door_code
        return {"status": "success"}

    def revoke_door_code(self, access_token, room_number):
        self.credentials.pop(room_number, None)
        return {"status": "success"}

    def get_door_code(self, access_token, room_number):
        credentials = self.observed_credentials
        if credentials is None:
            credentials = self.credentials
        return credentials.get(room_number)

    def close(self):
        pass


class ReconciliationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path_patch = patch("database.DB_PATH", Path(self.temp_dir.name) / "hotel.db")
        self.db_path_patch.start()
        self.addCleanup(self.db_path_patch.stop)
        self.db = Database()
        self.service = ReservationService(self.db)

        FakeTESAClient.initial_pins = {"pin1": "unrelated"}
        FakeTESAClient.instances = []
        FakeTTLockClient.credentials = {}
        FakeTTLockClient.observed_credentials = None
        FakeTTLockClient.instances = []

        tesa_patch = patch.object(sync, "TESAClient", FakeTESAClient)
        ttlock_patch = patch.object(sync, "TTLockClient", FakeTTLockClient)
        tesa_patch.start()
        ttlock_patch.start()
        self.addCleanup(tesa_patch.stop)
        self.addCleanup(ttlock_patch.stop)

    def _add_reservation(self, reservation_id, room_number, door_code, source_status="accepted"):
        now = datetime.now()
        self.db.upsert_reservation({
            "reservation_id": reservation_id,
            "guest_name": "Test Guest",
            "room_number": room_number,
            "door_code": door_code,
            "check_in": (now - timedelta(days=1)).isoformat(),
            "check_out": (now + timedelta(days=1)).isoformat(),
            "source_status": source_status,
            "lifecycle_status": "unknown",
            "event_hash": reservation_id,
        })

    def _move_reservation(self, reservation_id, room_number, door_code):
        now = datetime.now()
        self.service.upsert_reservation({
            "action": "move_reservation",
            "reservation_id": reservation_id,
            "data": {
                "reservation": {
                    "status": "accepted",
                    "checkIn": (now - timedelta(days=1)).date().isoformat(),
                    "checkOut": (now + timedelta(days=1)).date().isoformat(),
                    "planned_arrival": "14:00:00",
                    "planned_departure": "10:00:00",
                    "custom_fields": [{"name": "door_code", "value": door_code}],
                },
                "listing": {"nickname": room_number},
                "guest": {"name": "Test Guest"},
            },
        })

    def test_reconcile_applies_desired_access_to_fake_providers_and_persists_state(self):
        self._add_reservation("active-1", "2", "4826")

        self.service.reconcile()

        tesa_client = FakeTESAClient.instances[0]
        self.assertEqual(tesa_client.pins["pin6"], "4826")
        self.assertEqual(tesa_client.pins["pin1"], "unrelated")
        self.assertEqual(FakeTTLockClient.credentials["2"], "4826")

        desired = self.db.list_access_state()
        actual = self.db.list_actual_state()
        self.assertEqual(len(desired), 2)
        self.assertEqual(
            {(row["provider"], row["desired_value"], row["should_exist"]) for row in desired},
            {("TESA", "4826", 1), ("TTLOCK", "4826", 1)},
        )
        self.assertEqual(
            {(row["provider"], row["actual_value"]) for row in actual},
            {("TESA", "4826"), ("TTLOCK", "4826")},
        )
        self.assertEqual(self.db.list_mismatches(), [])
        self.assertEqual(self.db.get_reservation("active-1")["sync_state"], "succeeded")

    def test_read_current_lock_codes_reads_both_providers(self):
        FakeTESAClient.initial_pins = {"pin2": "tesa-code"}
        FakeTTLockClient.credentials = {"2": "ttlock-code", "6": "another-code"}

        lock_codes = sync.read_current_lock_codes()

        self.assertEqual(
            {(item["room_number"], item["provider"], item["door_code"]) for item in lock_codes},
            {
                ("1", "TESA", "tesa-code"),
                ("2", "TESA", ""),
                ("3", "TESA", ""),
                ("4", "TESA", ""),
                ("5", "TESA", ""),
                ("6", "TESA", ""),
                ("2", "TTLOCK", "ttlock-code"),
                ("6", "TTLOCK", "another-code"),
            },
        )

    def test_reconcile_clears_tesa_and_revokes_ttlock_for_cancelled_reservation(self):
        FakeTESAClient.initial_pins = {"pin6": "old-code"}
        FakeTTLockClient.credentials = {"2": "old-code"}
        self._add_reservation("cancelled-1", "2", "old-code", source_status="cancelled")

        self.service.reconcile()

        self.assertEqual(FakeTESAClient.instances[0].pins["pin6"], "")
        self.assertNotIn("2", FakeTTLockClient.credentials)
        self.assertTrue(all(row["should_exist"] == 0 for row in self.db.list_access_state()))
        self.assertTrue(all(row["actual_value"] == "" for row in self.db.list_actual_state()))
        self.assertEqual(self.db.get_reservation("cancelled-1")["sync_state"], "succeeded")

    def test_partial_ttlock_failure_marks_only_affected_reservation_failed(self):
        self._add_reservation("ttlock-failure", "2", "4826")
        self._add_reservation("tesa-only", "1", "9153")
        with patch.object(sync, "_retry_ttlock_update", side_effect=RuntimeError("provider unavailable")):
            self.service.reconcile()

        failed = self.db.get_reservation("ttlock-failure")
        unaffected = self.db.get_reservation("tesa-only")
        self.assertEqual(failed["sync_state"], "failed")
        self.assertEqual(failed["sync_provider"], "TTLOCK")
        self.assertEqual(unaffected["sync_state"], "succeeded")
        self.assertEqual(unaffected["sync_provider"], "TESA")
        actual_rows = self.db.list_actual_state()
        self.assertEqual(
            {(row["reservation_id"], row["provider"]) for row in actual_rows},
            {("ttlock-failure", "TESA"), ("tesa-only", "TESA")},
        )

    def test_readback_mismatch_is_persisted_and_marks_reservation_failed(self):
        self._add_reservation("readback-mismatch", "2", "4826")
        FakeTTLockClient.observed_credentials = {"2": "wrong-code"}

        with self.assertLogs(level="INFO") as captured_logs:
            self.service.reconcile()

        reservation = self.db.get_reservation("readback-mismatch")
        ttlock_state = next(
            row for row in self.db.list_actual_state()
            if row["provider"] == "TTLOCK"
        )
        self.assertEqual(reservation["sync_state"], "failed")
        self.assertEqual(ttlock_state["actual_value"], "wrong-code")
        mismatches = self.db.list_mismatches()
        self.assertTrue(any(
            row["reservation_id"] == "readback-mismatch"
            and row["provider"] == "TTLOCK"
            and row["mismatch_type"] == "value_mismatch"
            for row in mismatches
        ))
        log_output = "\n".join(captured_logs.output)
        self.assertNotIn("4826", log_output)
        self.assertNotIn("wrong-code", log_output)

    def test_room_move_reconciles_old_room_revoke_and_new_room_access(self):
        self._add_reservation("move-1", "2", "old-code")
        FakeTESAClient.initial_pins = {"pin6": "old-code"}
        FakeTTLockClient.credentials = {"2": "old-code"}

        self._move_reservation("move-1", "6", "new-code")
        queued_access = self.db.list_access_state_for_reservation("move-1")
        self.assertTrue(any(row["room_number"] == "2" and row["should_exist"] == 0 for row in queued_access))

        self.service.reconcile()

        self.assertEqual(FakeTESAClient.instances[0].pins["pin6"], "")
        self.assertEqual(FakeTESAClient.instances[0].pins["pin7"], "new-code")
        self.assertNotIn("2", FakeTTLockClient.credentials)
        self.assertEqual(FakeTTLockClient.credentials["6"], "new-code")
        persisted = self.db.list_access_state_for_reservation("move-1")
        self.assertEqual({row["room_number"] for row in persisted}, {"6"})
        self.assertTrue(all(row["should_exist"] == 1 for row in persisted))
        self.assertEqual(self.db.get_reservation("move-1")["sync_state"], "succeeded")

    def test_room_move_revoke_remains_queued_until_provider_confirms_it(self):
        self._add_reservation("move-retry", "2", "old-code")
        FakeTESAClient.initial_pins = {"pin6": "old-code"}
        FakeTTLockClient.credentials = {"2": "old-code"}
        self._move_reservation("move-retry", "6", "new-code")

        original_update = sync._retry_ttlock_update

        def fail_old_room_revoke(ttlock, access_token, room_number, door_code, remove=False):
            if room_number == "2" and remove:
                raise RuntimeError("temporary revoke failure")
            return original_update(ttlock, access_token, room_number, door_code, remove)

        with patch.object(sync, "_retry_ttlock_update", side_effect=fail_old_room_revoke):
            self.service.reconcile()

        queued_access = self.db.list_access_state_for_reservation("move-retry")
        self.assertTrue(any(row["room_number"] == "2" and row["should_exist"] == 0 for row in queued_access))
        self.assertEqual(self.db.get_reservation("move-retry")["sync_state"], "failed")

        self.service.reconcile()

        self.assertNotIn("2", FakeTTLockClient.credentials)
        self.assertEqual(FakeTTLockClient.credentials["6"], "new-code")
        persisted = self.db.list_access_state_for_reservation("move-retry")
        self.assertEqual({row["room_number"] for row in persisted}, {"6"})
        self.assertEqual(self.db.get_reservation("move-retry")["sync_state"], "succeeded")

    def test_mismatch_query_reports_missing_stale_and_value_mismatch_only(self):
        cases = [
            ("missing", "1234", True, None),
            ("stale", "", False, "old-code"),
            ("wrong-value", "1234", True, "5678"),
            ("matching", "1234", True, "1234"),
        ]
        for reservation_id, desired, should_exist, actual in cases:
            self.db.replace_access_state_for_reservation(reservation_id, [{
                "room_number": "2",
                "provider": "TTLOCK",
                "credential_name": "room-2",
                "desired_value": desired,
                "should_exist": should_exist,
            }])
            self.db.replace_actual_state_for_reservation(reservation_id, [{
                "room_number": "2",
                "provider": "TTLOCK",
                "credential_name": "room-2",
                "desired_value": actual,
            }])

        mismatches = {
            row["reservation_id"]: row["mismatch_type"]
            for row in self.db.list_mismatches()
        }

        self.assertEqual(
            mismatches,
            {
                "missing": "missing",
                "stale": "stale",
                "wrong-value": "value_mismatch",
            },
        )

    def test_delete_old_reservations_removes_related_state_atomically(self):
        old_checkout = (datetime.now() - timedelta(days=45)).isoformat()
        recent_checkout = (datetime.now() - timedelta(days=10)).isoformat()
        for reservation_id, checkout in (
            ("expired", old_checkout),
            ("recent", recent_checkout),
        ):
            self.db.upsert_reservation({
                "reservation_id": reservation_id,
                "room_number": "2",
                "door_code": f"code-{reservation_id}",
                "check_in": (datetime.now() - timedelta(days=50)).isoformat(),
                "check_out": checkout,
                "source_status": "accepted",
                "lifecycle_status": "completed",
                "event_hash": reservation_id,
            })
            self.db.replace_access_state_for_reservation(reservation_id, [{
                "room_number": "2",
                "provider": "TTLOCK",
                "credential_name": "room-2",
                "desired_value": f"code-{reservation_id}",
                "should_exist": False,
            }])
            self.db.replace_actual_state_for_reservation(reservation_id, [{
                "room_number": "2",
                "provider": "TTLOCK",
                "credential_name": "room-2",
                "desired_value": f"code-{reservation_id}",
            }])

        self.db.delete_old_reservations()

        self.assertIsNone(self.db.get_reservation("expired"))
        self.assertIsNotNone(self.db.get_reservation("recent"))
        self.assertEqual(
            {row["reservation_id"] for row in self.db.list_access_state()},
            {"recent"},
        )
        self.assertEqual(
            {row["reservation_id"] for row in self.db.list_actual_state()},
            {"recent"},
        )

    def test_upcoming_reservations_query_filters_checkout_date_and_fields(self):
        today = datetime.now().date()
        records = [
            ("past", today - timedelta(days=1)),
            ("today", today),
            ("future", today + timedelta(days=2)),
        ]
        for reservation_id, checkout_date in records:
            self.db.upsert_reservation({
                "reservation_id": reservation_id,
                "guest_name": "Private Guest",
                "room_number": "2",
                "door_code": f"code-{reservation_id}",
                "check_in": (checkout_date - timedelta(days=1)).isoformat(),
                "check_out": checkout_date.isoformat(),
                "source_status": "accepted",
                "lifecycle_status": "active",
                "event_hash": reservation_id,
                "sync_error": "private sync detail",
            })

        upcoming = self.db.list_reservations_checking_out_on_or_after(today)

        self.assertEqual([row["reservation_id"] for row in upcoming], ["today", "future"])
        self.assertEqual(
            set(upcoming[0]),
            {"reservation_id", "room_number", "check_in", "check_out", "lifecycle_status", "door_code"},
        )


class TTLockClientReadbackTests(unittest.TestCase):
    def test_get_door_code_pages_and_matches_configured_password_id(self):
        client = TTLockClient.__new__(TTLockClient)
        client.client = Mock()
        client.client.post.side_effect = [
            Mock(
                json=lambda: {
                    "list": [{"keyboardPwdId": "other", "keyboardPwd": "0000"}],
                    "pages": 2,
                },
                raise_for_status=lambda: None,
            ),
            Mock(
                json=lambda: {
                    "list": [{"keyboardPwdId": "pwd-2", "keyboardPwd": "4826"}],
                    "pages": 2,
                },
                raise_for_status=lambda: None,
            ),
        ]

        with (
            patch("ttlock_client.TTLOCK_ROOM2_LOCK_ID", "lock-2"),
            patch("ttlock_client.TTLOCK_ROOM2_PWD_ID", "pwd-2"),
        ):
            self.assertEqual(client.get_door_code("fake-token", "2"), "4826")

        self.assertEqual(client.client.post.call_count, 2)
        first_request = client.client.post.call_args_list[0]
        self.assertEqual(first_request.args[0], "/v3/lock/listKeyboardPwd")
        self.assertEqual(first_request.kwargs["data"]["lockId"], "lock-2")
        self.assertEqual(first_request.kwargs["data"]["pageNo"], 1)

    def test_get_door_code_errors_when_matched_entry_omits_keyboard_pwd(self):
        client = TTLockClient.__new__(TTLockClient)
        client.client = Mock()
        client.client.post.return_value = Mock(
            json=lambda: {
                "list": [{"keyboardPwdId": "pwd-2"}],
                "pages": 1,
            },
            raise_for_status=lambda: None,
        )

        with (
            patch("ttlock_client.TTLOCK_ROOM2_LOCK_ID", "lock-2"),
            patch("ttlock_client.TTLOCK_ROOM2_PWD_ID", "pwd-2"),
            self.assertRaisesRegex(ValueError, "missing keyboardPwd"),
        ):
            client.get_door_code("fake-token", "2")

    def test_get_door_code_errors_when_response_list_is_missing(self):
        client = TTLockClient.__new__(TTLockClient)
        client.client = Mock()
        client.client.post.return_value = Mock(
            json=lambda: {"pages": 1},
            raise_for_status=lambda: None,
        )

        with (
            patch("ttlock_client.TTLOCK_ROOM2_LOCK_ID", "lock-2"),
            patch("ttlock_client.TTLOCK_ROOM2_PWD_ID", "pwd-2"),
            self.assertRaisesRegex(ValueError, "missing a valid list"),
        ):
            client.get_door_code("fake-token", "2")

    def test_readback_retries_at_spaced_intervals_until_code_is_visible(self):
        ttlock = Mock()
        ttlock.get_door_code.side_effect = ["", "4826"]

        with patch.object(sync.time, "sleep") as sleep:
            actual = sync._read_ttlock_door_code_with_retry(
                ttlock,
                "fake-token",
                "2",
                "4826",
            )

        self.assertEqual(actual, "4826")
        self.assertEqual(ttlock.get_door_code.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_readback_waits_for_delayed_revoke_without_repeating_write(self):
        ttlock = Mock()
        ttlock.get_door_code.side_effect = ["4826", None]

        with patch.object(sync.time, "sleep") as sleep:
            actual = sync._read_ttlock_door_code_with_retry(
                ttlock,
                "fake-token",
                "2",
                "",
            )

        self.assertEqual(actual, "")
        self.assertEqual(ttlock.get_door_code.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_readback_returns_final_mismatch_after_bounded_spaced_queries(self):
        ttlock = Mock()
        ttlock.get_door_code.side_effect = ["wrong-1", "wrong-2", "wrong-3"]

        with patch.object(sync.time, "sleep") as sleep:
            actual = sync._read_ttlock_door_code_with_retry(
                ttlock,
                "fake-token",
                "2",
                "4826",
            )

        self.assertEqual(actual, "wrong-3")
        self.assertEqual(ttlock.get_door_code.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])

    def test_get_door_code_returns_none_when_id_is_absent_from_valid_response(self):
        client = TTLockClient.__new__(TTLockClient)
        client.client = Mock()
        client.client.post.return_value = Mock(
            json=lambda: {"list": [], "pages": 1},
            raise_for_status=lambda: None,
        )

        with (
            patch("ttlock_client.TTLOCK_ROOM2_LOCK_ID", "lock-2"),
            patch("ttlock_client.TTLOCK_ROOM2_PWD_ID", "pwd-2"),
        ):
            self.assertIsNone(client.get_door_code("fake-token", "2"))


if __name__ == "__main__":
    unittest.main()
