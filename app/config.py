from dotenv import load_dotenv
import os


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


load_dotenv()

TESA_BASE_URL = os.getenv("TESA_BASE_URL")
TESA_USERNAME = os.getenv("TESA_USERNAME")
TESA_PASSWORD = os.getenv("TESA_PASSWORD")
TESA_VERIFY_SSL = _get_bool("TESA_VERIFY_SSL", False)

TTLOCK_BASE_URL = os.getenv("TTLOCK_BASE_URL")
TTLOCK_VERIFY_SSL = _get_bool("TTLOCK_VERIFY_SSL", True)

TTLOCK_CLIENT_ID = os.getenv("TTLOCK_CLIENT_ID")
TTLOCK_CLIENT_SECRET = os.getenv("TTLOCK_CLIENT_SECRET")
TTLOCK_USERNAME = os.getenv("TTLOCK_USERNAME")
TTLOCK_PASSWORD_MD5 = os.getenv("TTLOCK_PASSWORD_MD5")

TTLOCK_ROOM2_LOCK_ID = os.getenv("TTLOCK_ROOM2_LOCK_ID")
TTLOCK_ROOM2_PWD_ID = os.getenv("TTLOCK_ROOM2_PWD_ID")
TTLOCK_ROOM6_LOCK_ID = os.getenv("TTLOCK_ROOM6_LOCK_ID")
TTLOCK_ROOM6_PWD_ID = os.getenv("TTLOCK_ROOM6_PWD_ID")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
HEALTHCHECKS_URL = os.getenv("HEALTHCHECKS_URL")