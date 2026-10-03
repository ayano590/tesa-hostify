import hashlib
import json
import logging
from datetime import datetime, timedelta

from .monitoring import DiscordNotifier
from .sync import sync_to_tesa, sync_to_ttlock

logger = logging.getLogger("reservation")
discord = DiscordNotifier()

CHECKIN_HOUR = 14
CHECKOUT_HOUR = 10

ROOM_TO_PIN = {"1": "pin2", "2": "pin6", "3": "pin3", "4": "pin4", "5": "pin5", "6": "pin7"}
SUPPORTED_PROVIDER_ROOM_IDS = {"2", "6"}


class ReservationService:
    def __init__(self, db):
        self.db = db

    def _event_hash(self, payload):
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def _normalize_date(self, value):
        if value in (None, "", "None"):
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _coerce_room_number(self, value):
        if value is None:
            return None
        return str(value).strip()

    def _extract_custom_door_code(self, payload):
        reservation = payload.get("data", {}).get("reservation", {}) if isinstance(payload.get("data"), dict) else {}
        custom_fields = reservation.get("custom_fields") or []
        for field in custom_fields:
            if isinstance(field, dict) and field.get("name") == "door_code":
                value = field.get("value")
                if value in (None, "None", ""):
                    return None
                return str(value)
        return None

    def _build_reservation_payload(self, payload):
        event_action = payload.get("action", "unknown")
        reservation_data = payload.get("data", {}).get("reservation", {}) if isinstance(payload.get("data"), dict) else {}
        listing = payload.get("data", {}).get("listing", {}) if isinstance(payload.get("data"), dict) else {}
        guest = payload.get("data", {}).get("guest", {}) if isinstance(payload.get("data"), dict) else {}

        reservation_id = str(payload.get("reservation_id") or "")
        room_number = self._coerce_room_number(listing.get("nickname") or payload.get("room_number"))

        check_in_raw = reservation_data.get("checkIn") or payload.get("checkIn")
        check_out_raw = reservation_data.get("checkOut") or payload.get("checkOut")

        planned_arrival = reservation_data.get("planned_arrival") or payload.get("planned_arrival")
        planned_departure = reservation_data.get("planned_departure") or payload.get("planned_departure")

        if planned_arrival in ["00:00:00", "None", None, ""]:
            planned_arrival = f"{CHECKIN_HOUR}:00:00"
        if planned_departure in ["00:00:00", "None", None, ""]:
            planned_departure = f"{CHECKOUT_HOUR}:00:00"

        check_in = self._normalize_date(f"{check_in_raw}T{planned_arrival}") if check_in_raw else None
        check_out = self._normalize_date(f"{check_out_raw}T{planned_departure}") if check_out_raw else None

        status = reservation_data.get("status") or payload.get("status_code") or "unknown"
        door_code = self._extract_custom_door_code(payload)

        return {
            "reservation_id": reservation_id,
            "guest_name": guest.get("name"),
            "room_number": room_number,
            "door_code": door_code,
            "check_in": check_in.isoformat() if check_in else None,
            "check_out": check_out.isoformat() if check_out else None,
            "source_status": status,
            "lifecycle_status": self._compute_status({
                "status": status,
                "check_in": check_in.isoformat() if check_in else None,
                "check_out": check_out.isoformat() if check_out else None,
            }, datetime.now()),
            "event_hash": self._event_hash(payload),
            "desired_access_state": "unknown",
            "sync_state": "unknown",
            "sync_provider": None,
            "sync_last_attempted_at": None,
            "sync_last_success_at": None,
            "sync_error": None,
            "action": event_action,
        }

    def upsert_reservation(self, payload):
        normalized = self._build_reservation_payload(payload)
        reservation_id = normalized["reservation_id"]
        room_number = normalized["room_number"]

        if not reservation_id:
            logger.warning("Ignoring reservation event without reservation_id.")
            return

        try:
            existing = self.db.get_reservation(reservation_id)
            if existing and existing.get("event_hash") == normalized["event_hash"]:
                logger.info("Duplicate event ignored for reservation %s", reservation_id)
                return

            previous_room = existing.get("room_number") if existing else None
            previous_access = (
                self.db.list_access_state_for_reservation(reservation_id)
                if existing and previous_room != room_number
                else []
            )
            logger.info("Upsert reservation %s status=%s", reservation_id, normalized["source_status"])
            self.db.upsert_reservation(normalized)

            access_records = self._build_access_records({**normalized, "lifecycle_status": normalized.get("lifecycle_status", "unknown")})
            if previous_room and previous_room != room_number:
                revoke_records = self._build_access_records({
                    "reservation_id": reservation_id,
                    "room_number": previous_room,
                    "door_code": "",
                    "lifecycle_status": "cancelled",
                    "source_status": "room_moved",
                }, include_missing=True)
                access_records = self._with_pending_revocations(
                    access_records + revoke_records,
                    previous_access,
                )
                self.db.replace_access_state_for_reservation(reservation_id, access_records)
            else:
                self.db.replace_access_state_for_reservation(reservation_id, access_records)
        except Exception as error:
            discord.error(
                title="Reservation Upsert Error",
                description="Reservation data could not be saved. Check application logs.",
                fields=[
                    {
                        "name": "Room",
                        "value": room_number if room_number in ROOM_TO_PIN else "unknown",
                    },
                    {"name": "Error Type", "value": type(error).__name__},
                ],
            )
            logger.error("Error upserting reservation (%s).", type(error).__name__)

    def delete_old_reservations(self):
        try:
            logger.info("Deleting old reservations...")
            self.db.delete_old_reservations()
        except Exception as error:
            discord.error(
                title="Reservation cleanup failed",
                description="Expired reservation data could not be removed. Check application logs.",
            )
            logger.error("Error deleting old reservations (%s).", type(error).__name__)

    def _build_access_records(self, reservation, include_missing=False):
        room_number = str(reservation.get("room_number") or "")
        door_code = reservation.get("door_code")
        lifecycle = reservation.get("lifecycle_status") or "unknown"
        should_exist = lifecycle in {"accepted", "active"} and bool(door_code)

        records = []
        if room_number in SUPPORTED_PROVIDER_ROOM_IDS:
            records.append({
                "room_number": room_number,
                "provider": "TTLOCK",
                "credential_name": f"room-{room_number}",
                "desired_value": door_code if should_exist else "",
                "should_exist": should_exist,
                "reason": f"reservation lifecycle={lifecycle}",
            })

        pin_name = ROOM_TO_PIN.get(room_number)
        if pin_name:
            records.append({
                "room_number": room_number,
                "provider": "TESA",
                "credential_name": pin_name,
                "desired_value": door_code if should_exist else "",
                "should_exist": should_exist,
                "reason": f"reservation lifecycle={lifecycle}",
            })

        if include_missing and not room_number:
            return records

        if include_missing and not records:
            return [{
                "room_number": room_number,
                "provider": "TTLOCK",
                "credential_name": f"room-{room_number or 'unknown'}",
                "desired_value": "",
                "should_exist": False,
                "reason": f"reservation lifecycle={lifecycle}",
            }]

        return records

    def _desired_access_for_reservation(self, reservation):
        return self._build_access_records(reservation, include_missing=False)

    def _access_record_key(self, record):
        return (
            str(record.get("room_number") or ""),
            record.get("provider"),
            record.get("credential_name"),
        )

    def _with_pending_revocations(self, desired, persisted):
        desired_keys = {self._access_record_key(record) for record in desired}
        merged = list(desired)
        for record in persisted:
            if not record.get("should_exist") and self._access_record_key(record) not in desired_keys:
                merged.append({
                    "room_number": record.get("room_number"),
                    "provider": record.get("provider"),
                    "credential_name": record.get("credential_name"),
                    "desired_value": record.get("desired_value") or "",
                    "should_exist": False,
                    "reason": record.get("reason") or "pending revoke",
                })
        return merged

    def reconcile(self):
        try:
            reservations = self.db.list_all_reservations()
        except Exception as error:
            discord.error(
                title="Reconciliation could not list reservations",
                description="The reservation list could not be read from the database.",
            )
            logger.error("Error listing all reservations (%s).", type(error).__name__)
            return

        now = datetime.now()
        desired_access = []
        desired_by_reservation = {}

        for reservation in reservations:
            lifecycle = self._compute_status(reservation, now)
            if reservation.get("lifecycle_status") != lifecycle:
                self.db.update_lifecycle_status(reservation["reservation_id"], lifecycle)
                reservation["lifecycle_status"] = lifecycle

            current_desired = self._build_access_records(
                {**reservation, "lifecycle_status": lifecycle}
            )
            persisted_access = self.db.list_access_state_for_reservation(
                reservation["reservation_id"]
            )
            desired = self._with_pending_revocations(current_desired, persisted_access)
            desired_by_reservation[reservation["reservation_id"]] = {
                "current": current_desired,
                "reconcile": desired,
            }
            desired_access.extend(desired)
            self.db.replace_access_state_for_reservation(
                reservation["reservation_id"],
                desired,
            )

        if not desired_access:
            logger.info("No desired access changes to reconcile.")
            return

        logger.info(f"Reconciling {len(desired_access)} desired access entries.")
        sync_result_tesa = sync_to_tesa(desired_access)
        sync_result_ttlock = sync_to_ttlock(desired_access)
        provider_results = {
            "TESA": sync_result_tesa,
            "TTLOCK": sync_result_ttlock,
        }

        for reservation in reservations:
            desired_state = desired_by_reservation[reservation["reservation_id"]]
            desired = desired_state["reconcile"]
            if not desired:
                continue
            state = "succeeded" if any(item.get("should_exist") for item in desired) or any(item.get("desired_value") == "" for item in desired) else "unknown"
            providers = {item.get("provider") for item in desired}
            observed_by_key = {
                (
                    item.get("provider"),
                    str(item.get("room_number", "")),
                    item.get("credential_name"),
                ): item.get("actual_value")
                for provider in providers
                for item in provider_results.get(provider, {}).get("actual_state", [])
            }
            actual_records = [
                {
                    "room_number": item.get("room_number"),
                    "provider": item.get("provider"),
                    "credential_name": item.get("credential_name"),
                    "actual_value": observed_by_key[
                        (
                            item.get("provider"),
                            str(item.get("room_number", "")),
                            item.get("credential_name"),
                        )
                    ],
                }
                for item in desired
                if (
                    item.get("provider"),
                    str(item.get("room_number", "")),
                    item.get("credential_name"),
                ) in observed_by_key
            ]
            self.db.upsert_actual_state_for_reservation(
                reservation["reservation_id"],
                actual_records,
            )
            failed_providers = [
                provider
                for provider in providers
                if provider_results.get(provider, {}).get("status") == "error"
                and (
                    not provider_results.get(provider, {}).get("failed_rooms")
                    or any(
                        str(item.get("room_number", "")) in provider_results[provider]["failed_rooms"]
                        for item in desired
                        if item.get("provider") == provider
                    )
                )
            ]
            mismatches = self.db.list_mismatches()
            if mismatches:
                mismatch_types = sorted({item["mismatch_type"] for item in mismatches})
                logger.warning(
                    "Detected %d reconciliation mismatches (%s).",
                    len(mismatches),
                    ", ".join(mismatch_types),
                )
            if failed_providers:
                provider = ",".join(sorted(failed_providers))
                self.db.mark_sync_failed(
                    reservation["reservation_id"],
                    provider=provider,
                    error=f"reconciliation failed for {provider} sync",
                )
                self.db.update_sync_state(
                    reservation["reservation_id"],
                    "failed",
                    provider=provider,
                    desired_access_state=json.dumps(desired, sort_keys=True),
                    error=f"reconciliation failed for {provider} sync",
                )
                continue
            self.db.mark_sync_success(
                reservation["reservation_id"],
                provider=",".join(sorted(providers)),
                desired_access_state=json.dumps(desired, sort_keys=True),
            )
            self.db.update_sync_state(
                reservation["reservation_id"],
                state,
                provider=",".join(sorted(providers)),
                desired_access_state=json.dumps(desired, sort_keys=True),
                error=None,
            )
            self.db.replace_access_state_for_reservation(
                reservation["reservation_id"],
                desired_state["current"],
            )

    def process_status_changes(self):
        try:
            logger.info("Processing reservation status changes...")
            reservations = self.db.list_all_reservations()
        except Exception as error:
            discord.error(
                title="Reservation status update failed",
                description="Reservation lifecycle statuses could not be recalculated.",
            )
            logger.error("Error listing reservations for status update (%s).", type(error).__name__)
            return

        now = datetime.now()
        for reservation in reservations:
            new_status = self._compute_status(reservation, now)
            if reservation.get("lifecycle_status") != new_status:
                logger.info(
                    "Updating reservation %s lifecycle to %s.",
                    reservation["reservation_id"],
                    new_status,
                )
                self.db.update_lifecycle_status(reservation["reservation_id"], new_status)

    def _compute_status(self, r, now):
        check_in = self._normalize_date(r.get("check_in"))
        check_out = self._normalize_date(r.get("check_out"))
        source_status = str(r.get("source_status") or r.get("status") or "").lower()

        if source_status == "cancelled":
            return "cancelled"

        if check_in is None or check_out is None:
            return "unknown"

        if now < check_in - timedelta(hours=1):
            return "accepted"

        if check_in <= now <= check_out:
            return "active"

        if now > check_out:
            return "completed"

        return "unknown"

    def truncate_WAL(self):
        try:
            logger.info("Truncating WAL file...")
            self.db.truncate_WAL()
        except Exception as error:
            discord.error(
                title="Database maintenance failed",
                description="The SQLite write-ahead log could not be checkpointed.",
            )
            logger.error("Error truncating WAL file (%s).", type(error).__name__)
