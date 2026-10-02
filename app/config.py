import os
from urllib.parse import urlparse

from dotenv import load_dotenv


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def validate_config() -> None:
    required = {
        "READ_API_TOKEN": READ_API_TOKEN,
        "TESA_USERNAME": TESA_USERNAME,
        "TESA_PASSWORD": TESA_PASSWORD,
        "TTLOCK_CLIENT_ID": TTLOCK_CLIENT_ID,
        "TTLOCK_CLIENT_SECRET": TTLOCK_CLIENT_SECRET,
        "TTLOCK_USERNAME": TTLOCK_USERNAME,
        "TTLOCK_PASSWORD_MD5": TTLOCK_PASSWORD_MD5,
        "TTLOCK_ROOM2_LOCK_ID": TTLOCK_ROOM2_LOCK_ID,
        "TTLOCK_ROOM2_PWD_ID": TTLOCK_ROOM2_PWD_ID,
        "TTLOCK_ROOM6_LOCK_ID": TTLOCK_ROOM6_LOCK_ID,
        "TTLOCK_ROOM6_PWD_ID": TTLOCK_ROOM6_PWD_ID,
    }
    missing = [name for name, value in required.items() if not value or not value.strip()]

    invalid = []
    if READ_API_TOKEN and len(READ_API_TOKEN) < 32:
        invalid.append("READ_API_TOKEN")

    for name in ("TESA_BASE_URL", "TTLOCK_BASE_URL"):
        value = globals()[name]
        if value:
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                invalid.append(name)

    for name in ("TESA_VERIFY_SSL", "TTLOCK_VERIFY_SSL"):
        raw_value = os.getenv(name)
        if raw_value is not None and raw_value.strip().lower() not in {
            "1", "0", "true", "false", "yes", "no", "on", "off",
        }:
            invalid.append(name)

    errors = []
    if missing:
        errors.append("Missing required environment variables: " + ", ".join(missing))
    if invalid:
        errors.append("Invalid configuration values for: " + ", ".join(invalid))
    if errors:
        raise ValueError("; ".join(errors))


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
READ_API_TOKEN = os.getenv("READ_API_TOKEN")