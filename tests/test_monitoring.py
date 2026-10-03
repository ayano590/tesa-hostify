import os
import sys
import unittest
from unittest.mock import Mock

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from app.monitoring import DiscordNotifier, Heartbeat


class MonitoringTests(unittest.TestCase):
    def test_discord_delivery_is_skipped_when_webhook_is_not_configured(self):
        notifier = DiscordNotifier()
        self.addCleanup(notifier.close)
        notifier.webhook_url = None
        notifier.client.post = Mock()

        notifier.error("Failure", "Safe summary")

        notifier.client.post.assert_not_called()

    def test_discord_delivery_logs_no_webhook_url_or_response_body(self):
        secret = "discord-webhook-secret"
        notifier = DiscordNotifier()
        self.addCleanup(notifier.close)
        notifier.webhook_url = f"https://discord.example/{secret}"
        request = httpx.Request("POST", notifier.webhook_url)
        response = httpx.Response(
            500,
            request=request,
            text=f"provider response contained {secret}",
        )
        notifier.client.post = Mock(return_value=response)

        with self.assertLogs("monitor", level="ERROR") as captured:
            notifier.error("Failure", "Safe summary")

        output = "\n".join(captured.output)
        self.assertNotIn(secret, output)
        self.assertNotIn(response.text, output)
        self.assertIn("HTTP 500", output)

    def test_discord_request_error_does_not_log_webhook_url(self):
        secret = "discord-webhook-secret"
        notifier = DiscordNotifier()
        self.addCleanup(notifier.close)
        notifier.webhook_url = f"https://discord.example/{secret}"
        notifier.client.post = Mock(
            side_effect=httpx.RequestError(
                "request failed",
                request=httpx.Request("POST", notifier.webhook_url),
            )
        )

        with self.assertLogs("monitor", level="ERROR") as captured:
            notifier.error("Failure", "Safe summary")

        self.assertNotIn(secret, "\n".join(captured.output))

    def test_heartbeat_notifies_only_on_outage_and_recovery_transitions(self):
        heartbeat = Heartbeat()
        self.addCleanup(heartbeat.close)
        heartbeat.url = "https://health.example/ping"
        heartbeat.discord.close()
        heartbeat.discord = Mock()
        heartbeat.client.get = Mock(
            side_effect=httpx.RequestError(
                "request failed",
                request=httpx.Request("GET", "https://health.example/ping"),
            )
        )

        heartbeat.ping()
        heartbeat.ping()
        self.assertEqual(heartbeat.discord.warning.call_count, 1)
        heartbeat.discord.info.assert_not_called()

        heartbeat.client.get = Mock(
            return_value=httpx.Response(
                200,
                request=httpx.Request("GET", heartbeat.url),
            )
        )
        heartbeat.ping()
        heartbeat.ping()

        heartbeat.discord.info.assert_called_once()
        heartbeat.discord.warning.assert_called_once()
