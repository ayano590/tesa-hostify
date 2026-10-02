from datetime import datetime
import logging

import httpx

from config import DISCORD_WEBHOOK_URL, HEALTHCHECKS_URL

logger = logging.getLogger("monitor")


class Heartbeat:
    def __init__(self):
        self.url = HEALTHCHECKS_URL
        self.client = httpx.Client(timeout=10)
        self.discord = DiscordNotifier()
        self._failure_reported = False

    def ping(self):
        if not self.url:
            return
        try:
            response = self.client.get(self.url)
            response.raise_for_status()
        except (httpx.HTTPError, ValueError) as error:
            logger.error("Heartbeat failed (%s).", type(error).__name__)
            if not self._failure_reported:
                self.discord.warning(
                    title="Health check unavailable",
                    description="The configured health-check endpoint could not be reached.",
                )
                self._failure_reported = True
            return
        if self._failure_reported:
            self.discord.info(
                title="Health check recovered",
                description="The configured health-check endpoint is responding again.",
            )
            self._failure_reported = False

    def close(self):
        self.client.close()
        self.discord.close()


class DiscordNotifier:
    def __init__(self):
        self.webhook_url = DISCORD_WEBHOOK_URL
        self.client = httpx.Client(timeout=10)

    def _send_embed(self, title: str, description: str, color: int, fields=None):
        if not self.webhook_url:
            return

        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.now().isoformat(),
        }
        if fields:
            embed["fields"] = fields

        payload = {"embeds": [embed]}
        try:
            response = self.client.post(self.webhook_url, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            logger.error(
                "Discord notification was rejected (HTTP %s).",
                error.response.status_code,
            )
        except (httpx.HTTPError, ValueError) as error:
            logger.error("Discord notification delivery failed (%s).", type(error).__name__)

    def info(self, title: str, description: str, fields=None):
        self._send_embed(title, description, color=0x3498db, fields=fields)

    def warning(self, title: str, description: str, fields=None):
        self._send_embed(title, description, color=0xf1c40f, fields=fields)

    def error(self, title: str, description: str, fields=None):
        self._send_embed(title, description, color=0xe74c3c, fields=fields)

    def close(self):
        self.client.close()