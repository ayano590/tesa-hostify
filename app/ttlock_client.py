import time

import httpx

from app.config import (
    TTLOCK_BASE_URL,
    TTLOCK_CLIENT_ID,
    TTLOCK_CLIENT_SECRET,
    TTLOCK_PASSWORD_MD5,
    TTLOCK_ROOM2_LOCK_ID,
    TTLOCK_ROOM2_PWD_ID,
    TTLOCK_ROOM6_LOCK_ID,
    TTLOCK_ROOM6_PWD_ID,
    TTLOCK_USERNAME,
    TTLOCK_VERIFY_SSL,
)


class TTLockClient:
    def __init__(self):
        self.client = httpx.Client(
            base_url=TTLOCK_BASE_URL or "https://euapi.ttlock.com",
            verify=TTLOCK_VERIFY_SSL,
            timeout=30,
        )

    def get_access_token(self):
        response = self.client.post(
            "/oauth2/token",
            json={
                "clientId": TTLOCK_CLIENT_ID,
                "clientSecret": TTLOCK_CLIENT_SECRET,
                "username": TTLOCK_USERNAME,
                "password": TTLOCK_PASSWORD_MD5,
            },
        )
        response.raise_for_status()
        return response.json().get("access_token")

    def _resolve_room_ids(self, room_number):
        if room_number == "2":
            return TTLOCK_ROOM2_LOCK_ID, TTLOCK_ROOM2_PWD_ID
        if room_number == "6":
            return TTLOCK_ROOM6_LOCK_ID, TTLOCK_ROOM6_PWD_ID
        raise ValueError(f"Unsupported TTLock room number: {room_number}")

    def update_door_code(self, access_token, room_number, door_code):
        current_ms = time.time_ns() // 1_000_000
        lock_id, pwd_id = self._resolve_room_ids(room_number)

        payload = {
            "clientId": TTLOCK_CLIENT_ID,
            "accessToken": access_token,
            "lockId": lock_id,
            "keyboardPwdId": pwd_id,
            "newKeyboardPwd": door_code,
            "changeType": 2,
            "date": current_ms,
        }

        response = self.client.post("/v3/keyboardPwd/change", data=payload)
        response.raise_for_status()
        return response.json()

    def revoke_door_code(self, access_token, room_number):
        current_ms = time.time_ns() // 1_000_000
        lock_id, pwd_id = self._resolve_room_ids(room_number)

        payload = {
            "clientId": TTLOCK_CLIENT_ID,
            "accessToken": access_token,
            "lockId": lock_id,
            "keyboardPwdId": pwd_id,
            "deleteType": 2,
            "date": current_ms,
        }

        response = self.client.post("/v3/keyboardPwd/delete", data=payload)
        response.raise_for_status()
        return response.json()

    def get_door_code(self, access_token, room_number):
        lock_id, pwd_id = self._resolve_room_ids(room_number)
        if not lock_id or not pwd_id:
            raise ValueError(f"TTLock lock/password IDs are not configured for room {room_number}")

        page_no = 1
        page_size = 100

        while True:
            response = self.client.post(
                "/v3/lock/listKeyboardPwd",
                data={
                    "clientId": TTLOCK_CLIENT_ID,
                    "accessToken": access_token,
                    "lockId": lock_id,
                    "pageNo": page_no,
                    "pageSize": page_size,
                    "orderBy": "0",
                    "date": time.time_ns() // 1_000_000,
                },
            )
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError("TTLock keyboard-password response must be an object")

            credentials = result.get("list")
            if not isinstance(credentials, list):
                raise ValueError("TTLock keyboard-password response is missing a valid list")

            for credential in credentials:
                if not isinstance(credential, dict):
                    raise ValueError("TTLock keyboard-password list contains an invalid entry")
                if str(credential.get("keyboardPwdId")) == str(pwd_id):
                    if "keyboardPwd" not in credential or credential["keyboardPwd"] is None:
                        raise ValueError(
                            "TTLock keyboard-password response is missing "
                            f"keyboardPwd for configured password ID {pwd_id}"
                        )
                    return credential["keyboardPwd"]

            try:
                total_pages = int(result["pages"])
            except (KeyError, TypeError, ValueError) as e:
                raise ValueError("TTLock keyboard-password response is missing a valid pages count") from e
            if total_pages < 1:
                raise ValueError("TTLock keyboard-password response has an invalid pages count")
            if page_no >= total_pages:
                return None
            page_no += 1

    def close(self):
        self.client.close()
