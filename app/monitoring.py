from datetime import datetime
from config import DISCORD_WEBHOOK_URL, HEALTHCHECKS_URL
import httpx
import logging

logger = logging.getLogger("monitor")

class Heartbeat:
    def __init__(self):
        self.url = HEALTHCHECKS_URL
        self.client = httpx.Client(timeout=10)

    def ping(self):
        try:
            response = self.client.get(self.url or "https://hc-ping.com/3de22dcd-bde0-4108-ab2d-83e11123e0b7")
            response.raise_for_status()
        except:
            logger.error("Heartbeat failed")

class DiscordNotifier:
    def __init__(self):
        self.webhook_url = DISCORD_WEBHOOK_URL
        self.client = httpx.Client(timeout=10)

    def _send_embed(self, title: str, description: str, color: int, fields=None):
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
            response = self.client.post(self.webhook_url or "", json=payload)
            response.raise_for_status()
        except httpx.RequestError as e:
            logger.error(f"An error occurred while sending the Discord notification: {e}")
        except httpx.HTTPStatusError as e:
            logger.error(f"Discord returned an error response: {e.response.status_code} - {e.response.text}")

    def info(self, title: str, description: str, fields=None):
        self._send_embed(title, description, color=0x3498db, fields=fields)

    def warning(self, title: str, description: str, fields=None):
        self._send_embed(title, description, color=0xf1c40f, fields=fields)

    def error(self, title: str, description: str, fields=None):
        self._send_embed(title, description, color=0xe74c3c, fields=fields)

    def close(self):
        self.client.close()