import httpx

from app.config import TESA_BASE_URL, TESA_USERNAME, TESA_PASSWORD, TESA_VERIFY_SSL


class TESAClient:
    def __init__(self):
        self.client = httpx.Client(
            base_url=TESA_BASE_URL or "https://localhost:8181/TesaHotelPlatform/REST",
            verify=TESA_VERIFY_SSL,
            timeout=30,
        )

    def login(self):
        response = self.client.post(
            "/user/login",
            json={"userName": TESA_USERNAME, "password": TESA_PASSWORD},
        )
        response.raise_for_status()
        return response.json()

    def get_common_pins(self):
        response = self.client.get("/systemConfig/commonPins")
        response.raise_for_status()
        return response.json()

    def update_common_pins(self, pins: dict):
        response = self.client.post("/systemConfig/commonPins", json=pins)
        response.raise_for_status()
        return response.json()

    def close(self):
        self.client.close()
