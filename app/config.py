from dotenv import load_dotenv
import os

load_dotenv()

TESA_BASE_URL = os.getenv("TESA_BASE_URL")
TESA_USERNAME = os.getenv("TESA_USERNAME")
TESA_PASSWORD = os.getenv("TESA_PASSWORD")