from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class CreateLeadCommand:
    brand_key: str
    form_type: str
    full_name: str
    email: str
    phone: str
    privacy_accepted: bool
    source_key: str | None = None
    phone_country: str | None = None
    organization_name: str | None = None
    job_title: str | None = None
    message: str | None = None
    form_data: dict[str, Any] = field(default_factory=dict)
    source_url: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None
    device_type: str | None = None
    classification: str | None = None
    assigned_to: str | None = None
    next_follow_up_at: datetime | None = None
    education_level: str | None = None
    grade: str | None = None
    contact_reason: str | None = None

    def as_persistence_data(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}
