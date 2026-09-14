import logging

from tenacity import retry, stop_after_attempt, wait_exponential

from monitoring import DiscordNotifier
from tesa_client import TESAClient
from ttlock_client import TTLockClient

logger = logging.getLogger("sync")
discord = DiscordNotifier()

PIN_KEYS = ["pin1", "pin2", "pin3", "pin4", "pin5", "pin6", "pin7"]
ROOM_TO_PIN = {"1": "pin2", "2": "pin6", "3": "pin3", "4": "pin4", "5": "pin5", "6": "pin7"}


def normalize_pin_value(value):
    if value is None:
        return ""
    value = str(value).strip()
    return value if value else ""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _execute_tesa_sync(tesa, desired_pins):
    logger.info("Logging into TESA...")
    tesa.login()
    logger.info("Login successful.")

    current_pins = tesa.get_common_pins().get("commonPinsInfo", {})
    current_map = {str(k).lower(): normalize_pin_value(v) for k, v in current_pins.items() if str(k).lower().startswith("pin")}
    normalized_target = {str(k).lower(): normalize_pin_value(v) for k, v in desired_pins.items() if str(k).lower().startswith("pin")}

    if current_map == normalized_target:
        logger.info("No changes to sync with TESA.")
        return {"status": "no_changes"}

    merged = dict(current_map)
    merged.update(normalized_target)
    for key in list(merged):
        if key.startswith("pin") and key not in normalized_target:
            merged[key] = current_map.get(key, "")

    for key, value in normalized_target.items():
        merged[key] = value

    tesa.update_common_pins({**current_pins, **{key: value for key, value in merged.items()}})
    logger.info("TESA update success.")
    return {"status": "success"}


def sync_to_tesa(desired_access):
    desired_pins = {}
    for item in desired_access or []:
        if item.get("provider") != "TESA":
            continue
        room_number = str(item.get("room_number", ""))
        pin_name = ROOM_TO_PIN.get(room_number)
        if pin_name is None:
            continue
        desired_pins[pin_name] = normalize_pin_value(item.get("desired_value", ""))

    logger.info(f"Syncing to TESA with target pins: {desired_pins}")
    tesa = TESAClient()

    try:
        return _execute_tesa_sync(tesa, desired_pins)
    except Exception as e:
        discord.error(title="Tesa sync error", description=str(e))
        logger.error(f"Error occurred while syncing to TESA after retries: {e}")
        return {"status": "error", "stage": "sync_failed"}
    finally:
        try:
            tesa.close()
            logger.info("TESA client closed.")
        except Exception as e:
            discord.warning(title="Tesa Close error", description=str(e))
            logger.warning("Error occurred while closing TESA client.")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _retry_ttlock_update(ttlock, access_token, room_number, door_code, remove=False):
    if remove:
        logger.info(f"Revoking door code for room {room_number}...")
        return ttlock.revoke_door_code(access_token, room_number)

    logger.info(f"Updating door code for room {room_number}...")
    return ttlock.update_door_code(access_token, room_number, door_code)


def sync_to_ttlock(desired_access):
    logger.info(f"Syncing to TTLock for desired access: {desired_access}")
    ttlock = TTLockClient()

    try:
        logger.info("Getting access token from TTLock...")
        access_token = ttlock.get_access_token()

        for item in desired_access or []:
            if item.get("provider") != "TTLOCK":
                continue

            room_number = str(item.get("room_number", ""))
            if room_number not in ["2", "6"]:
                logger.info(f"Skipping room {room_number}...")
                continue

            desired_value = item.get("desired_value")
            remove = bool(item.get("should_exist") is False or desired_value in (None, ""))

            try:
                _retry_ttlock_update(ttlock, access_token, room_number, desired_value, remove=remove)
            except Exception as e:
                discord.error(
                    title="TTLock sync error",
                    description=str(e),
                    fields=[{"name": "Room Number", "value": room_number}],
                )
                logger.error(f"Failed to sync room {room_number} after multiple retries: {e}")
                continue

        logger.info("TTLock update batch completed.")
        return {"status": "success"}
    except Exception as e:
        discord.error(title="TTLock critical error", description=str(e))
        logger.error(f"Critical error occurred while syncing to TTLock: {e}")
        return {"status": "error", "stage": "sync"}
    finally:
        try:
            ttlock.close()
            logger.info("TTLock client closed.")
        except Exception as e:
            discord.warning(title="TTLock Close error", description=str(e))
            logger.warning("Error occurred while closing TTLock client.")
