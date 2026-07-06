import time
import httpx

from config import (
    TTLOCK_BASE_URL,
    TTLOCK_CLIENT_ID,
    TTLOCK_CLIENT_SECRET,
    TTLOCK_ROOM2_LOCK_ID,
    TTLOCK_ROOM2_PWD_ID,
    TTLOCK_ROOM6_LOCK_ID,
    TTLOCK_ROOM6_PWD_ID,
    TTLOCK_USERNAME,
    TTLOCK_PASSWORD_MD5)

class TTLockClient:
    def __init__(self):
        self.client = httpx.Client(base_url=TTLOCK_BASE_URL or "https://euapi.ttlock.com", verify=False, timeout=30)

    def get_access_token(self):
        response = self.client.post("/oauth2/token",json={
            "clientId": TTLOCK_CLIENT_ID,
            "clientSecret": TTLOCK_CLIENT_SECRET,
            "username": TTLOCK_USERNAME,
            "password": TTLOCK_PASSWORD_MD5})
        response.raise_for_status()
        return response.json().get("access_token")
    
    def update_door_code(self, access_token, room_number, door_code):
        current_ms = time.time_ns() // 1_000_000  # Current time in milliseconds

        if room_number == "2":
            lock_id = TTLOCK_ROOM2_LOCK_ID
            pwd_id = TTLOCK_ROOM2_PWD_ID
        else:  # room_number == "6"
            lock_id = TTLOCK_ROOM6_LOCK_ID
            pwd_id = TTLOCK_ROOM6_PWD_ID

        payload = {
            "clientId": TTLOCK_CLIENT_ID,
            "accessToken": access_token,
            "lockId": lock_id,
            "keyboardPwdId": pwd_id,
            "newKeyboardPwd": door_code,
            "changeType": 2,
            "date": current_ms
        }

        response = self.client.post("/v3/keyboardPwd/change", data=payload)
        response.raise_for_status()
        return response.json()

    def close(self):
        self.client.close()