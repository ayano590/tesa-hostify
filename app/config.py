from dotenv import load_dotenv
import os

load_dotenv()

PMS_BASE_URL = os.getenv("PMS_BASE_URL")
PMS_USERNAME = os.getenv("PMS_USERNAME")
PMS_PASSWORD = os.getenv("PMS_PASSWORD")