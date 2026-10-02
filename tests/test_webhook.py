import os
import sys
import unittest
from datetime import date
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

import database
import logging_setup
import monitoring


class FakeDatabase:
    pass


class FakeNotifier:
    def info(self, **kwargs):
        pass

    def error(self, **kwargs):
        pass

    def warning(self, **kwargs):
        pass


with (
    patch.object(database, "Database", FakeDatabase),
    patch.object(monitoring, "DiscordNotifier", FakeNotifier),
    patch.object(logging_setup, "setup_logging"),
):
    import main


class HostifyWebhookHTTPTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(main.router)
        self.client = TestClient(app)
        self.upsert_patch = patch.object(main.service, "upsert_reservation")
        self.upsert = self.upsert_patch.start()
        self.addCleanup(self.upsert_patch.stop)

    def _authorized_headers(self):
        return {"Authorization": f"Bearer {'r' * 32}"}

    def test_malformed_json_returns_400(self):
        response = self.client.post(
            "/webhook/hostify",
            content=b'{"action":',
            headers={"content-type": "application/json"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Request body must contain valid JSON.")
        self.upsert.assert_not_called()

    def test_invalid_payload_shape_returns_422_without_echoing_payload(self):
        response = self.client.post(
            "/webhook/hostify",
            json={"action": "new_reservation", "data": "door-code-secret"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "Webhook payload is invalid.")
        self.assertNotIn("door-code-secret", response.text)
        self.upsert.assert_not_called()

    def test_reservation_action_without_id_returns_422(self):
        response = self.client.post(
            "/webhook/hostify",
            json={"action": "new_reservation"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "reservation_id is required.")
        self.upsert.assert_not_called()

    def test_unsupported_action_is_ignored(self):
        response = self.client.post(
            "/webhook/hostify",
            json={"action": "listing_photo_processed"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ignored")
        self.upsert.assert_not_called()

    def test_valid_reservation_is_accepted_and_enqueued(self):
        payload = {
            "action": "new_reservation",
            "reservation_id": "reservation-1",
            "data": {
                "reservation": {"status": "accepted"},
                "listing": {"nickname": "2"},
            },
        }
        response = self.client.post("/webhook/hostify", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.upsert.assert_called_once()
        self.assertEqual(self.upsert.call_args.args[0]["reservation_id"], "reservation-1")

    def test_enqueue_failure_returns_500(self):
        with patch.object(
            main.BackgroundTasks,
            "add_task",
            side_effect=RuntimeError("internal detail"),
        ):
            response = self.client.post(
                "/webhook/hostify",
                json={"action": "new_reservation", "reservation_id": "reservation-1"},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "Failed to process webhook.")
        self.assertNotIn("internal detail", response.text)


class ReadOnlyAPIHTTPTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(main.router)
        self.client = TestClient(app)
        self.token_patch = patch.object(main, "READ_API_TOKEN", "r" * 32)
        self.token_patch.start()
        self.addCleanup(self.token_patch.stop)

    def test_locks_endpoint_requires_bearer_token(self):
        with patch.object(main, "read_current_lock_codes") as read_locks:
            response = self.client.get("/api/locks")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["www-authenticate"], "Bearer")
        read_locks.assert_not_called()

    def test_read_endpoints_reject_an_incorrect_bearer_token(self):
        response = self.client.get(
            "/api/reservations",
            headers={"Authorization": f"Bearer {'x' * 32}"},
        )

        self.assertEqual(response.status_code, 401)

    def test_locks_endpoint_returns_current_codes_with_provider_labels(self):
        locks = [
            {"room_number": "2", "provider": "TESA", "door_code": "1234"},
            {"room_number": "2", "provider": "TTLOCK", "door_code": "5678"},
        ]
        with patch.object(main, "read_current_lock_codes", return_value=locks):
            response = self.client.get("/api/locks", headers=self._authorized_headers())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"locks": locks})
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_locks_endpoint_does_not_expose_provider_exception(self):
        with patch.object(
            main,
            "read_current_lock_codes",
            side_effect=RuntimeError("secret-provider-detail"),
        ):
            response = self.client.get("/api/locks", headers=self._authorized_headers())

        self.assertEqual(response.status_code, 502)
        self.assertNotIn("secret-provider-detail", response.text)

    def test_reservations_endpoint_requires_bearer_token(self):
        with patch.object(main.db, "list_reservations_checking_out_on_or_after", create=True) as query:
            response = self.client.get("/api/reservations")

        self.assertEqual(response.status_code, 401)
        query.assert_not_called()

    def test_reservations_endpoint_returns_selected_fields(self):
        reservations = [{
            "reservation_id": "reservation-1",
            "room_number": "2",
            "check_in": "2026-10-04T14:00:00",
            "check_out": "2026-10-06T10:00:00",
            "lifecycle_status": "accepted",
            "door_code": "4826",
        }]
        with patch.object(
            main.db,
            "list_reservations_checking_out_on_or_after",
            create=True,
            return_value=reservations,
        ) as query:
            response = self.client.get("/api/reservations", headers=self._authorized_headers())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"reservations": reservations})
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(query.call_args.args[0], date.today())

    def test_reservations_endpoint_returns_safe_error_on_database_failure(self):
        with patch.object(
            main.db,
            "list_reservations_checking_out_on_or_after",
            create=True,
            side_effect=RuntimeError("sensitive-db-detail"),
        ):
            response = self.client.get("/api/reservations", headers=self._authorized_headers())

        self.assertEqual(response.status_code, 500)
        self.assertNotIn("sensitive-db-detail", response.text)

    def _authorized_headers(self):
        return {"Authorization": f"Bearer {'r' * 32}"}


if __name__ == "__main__":
    unittest.main()
