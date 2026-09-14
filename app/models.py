from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HostifyCustomField(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: Optional[str] = None
    name: Optional[str] = None
    value: Optional[str] = None


class HostifyReservationPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Optional[str] = None
    checkIn: Optional[str] = None
    checkOut: Optional[str] = None
    planned_arrival: Optional[str] = None
    planned_departure: Optional[str] = None
    custom_fields: List[HostifyCustomField] = Field(default_factory=list)

    @field_validator("custom_fields", mode="before")
    @classmethod
    def normalize_custom_fields(cls, value: Any) -> List[HostifyCustomField]:
        if value is None:
            return []
        if isinstance(value, list):
            return [HostifyCustomField.model_validate(item) for item in value]
        return []


class HostifyGuest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = None


class HostifyListing(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nickname: Optional[str] = None


class HostifyReservationEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reservation: Optional[HostifyReservationPayload] = None
    listing: Optional[HostifyListing] = None
    guest: Optional[HostifyGuest] = None


class HostifyWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: Optional[str] = None
    reservation_id: Optional[str] = None
    data: Optional[HostifyReservationEnvelope] = None
    checkIn: Optional[str] = None
    checkOut: Optional[str] = None
    planned_arrival: Optional[str] = None
    planned_departure: Optional[str] = None
    status_code: Optional[str] = None

    @property
    def reservation_data(self) -> Dict[str, Any]:
        return self.data.model_dump(exclude_none=True) if self.data else {}


class DesiredAccessRecord(BaseModel):
    room_number: str
    provider: str
    credential_name: str
    desired_value: Optional[str] = None
    should_exist: bool = True
    reason: Optional[str] = None

    @property
    def target_value(self) -> Optional[str]:
        if self.desired_value is None:
            return None
        return self.desired_value.strip() if isinstance(self.desired_value, str) else self.desired_value


hostify_webhook_event_types = [
    "message_new",
    "move_reservation",
    "new_reservation",
    "update_reservation",
    "create_listing",
    "update_listing",
    "create_update_listing",
    "listing_photo_processed",
]
