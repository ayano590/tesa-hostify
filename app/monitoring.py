from datetime import datetime
from app.config import DISCORD_WEBHOOK_URL, HEALTHCHECKS_URL
import httpx
import logging
import json

logger = logging.getLogger("monitor")

class Heartbeat:
    def __init__(self):
        self.url = HEALTHCHECKS_URL
        self.client = httpx.Client(timeout=10)

    def ping(self):
        try:
            response = self.client.get(self.url or "")
            response.raise_for_status()
        except:
            logger.error("Heartbeat failed")

class DiscordNotifier:
    def __init__(self):
        self.webhook_url = DISCORD_WEBHOOK_URL
        self.client = httpx.Client(timeout=10)

    def _send_embed(self, title: str, description: str, color: int, fields=None) -> bool:
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
            return True
        except httpx.RequestError as e:
            logger.error(f"An error occurred while sending the Discord notification: {e}")
        except httpx.HTTPStatusError as e:
            logger.error(f"Discord returned an error response: {e.response.status_code} - {e.response.text}")
        return False

    def info(self, title: str, description: str, fields=None) -> bool:
        return self._send_embed(title, description, color=0x3498db, fields=fields)

    def warning(self, title: str, description: str, fields=None) -> bool:
        return self._send_embed(title, description, color=0xf1c40f, fields=fields)

    def error(self, title: str, description: str, fields=None) -> bool:
        return self._send_embed(title, description, color=0xe74c3c, fields=fields)

    def send_file(self, title: str, filename: str, content: str) -> bool:
        payload = {
            "content": title,
            "attachments": [{"id": 0, "filename": filename}],
        }
        try:
            response = self.client.post(
                self.webhook_url or "",
                data={"payload_json": json.dumps(payload)},
                files={"files[0]": (filename, content.encode("utf-8"), "text/csv")},
            )
            response.raise_for_status()
            return True
        except httpx.RequestError as e:
            logger.error(f"An error occurred while sending the Discord file: {e}")
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Discord returned an error response: {e.response.status_code} - {e.response.text}"
            )
        return False

    def close(self):
        self.client.close()