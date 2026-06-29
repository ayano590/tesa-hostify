import httpx

from config import PMS_BASE_URL, PMS_USERNAME, PMS_PASSWORD

class PMSClient:
    def __init__(self):
        self.client = httpx.Client(base_url=PMS_BASE_URL, verify=False, timeout=30)

    def login(self):
        response = self.client.post("/TesaHotelPlatform/REST/user/login", json={"userName": PMS_USERNAME, "password": PMS_PASSWORD})
        response.raise_for_status()
        return response.json()
    
    def close(self):
        self.client.close()