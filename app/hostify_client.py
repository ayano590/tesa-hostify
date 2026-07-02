from dotenv import load_dotenv
import os
import httpx
import logging

load_dotenv()

logger = logging.getLogger("Hostify")

HOSTIFY_ENDPOINT = os.getenv("HOSTIFY_ENDPOINT")
HOSTIFY_RESERVATIONS_API_KEY = os.getenv("HOSTIFY_RESERVATIONS_API_KEY")

def send_door_code_to_hostify(reservation_id, custom_field_id, door_code):

    url = f"{HOSTIFY_ENDPOINT}/reservations/custom_field_update"
    headers = {
        "accept": "*/*",
        "x-api-key": HOSTIFY_RESERVATIONS_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "reservation_id": int(reservation_id),
        "custom_field_id": int(custom_field_id),
        "value": str(door_code)
    }

    with httpx.Client() as client:
        try:
            logger.info(f"Sending door code to Hostify...")
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Error sending door code to Hostify: {e}")
            return {"status": "error", "reason": str(e)}