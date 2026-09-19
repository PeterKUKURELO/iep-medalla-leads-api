from __future__ import annotations

import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class ComplaintCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    complaint_type: Literal["complaint", "claim"] = Field(alias="complaintType")
    full_name: str = Field(alias="fullName", min_length=3, max_length=150)
    document_type: Literal["dni", "ce", "passport"] = Field(alias="documentType")
    document_number: str = Field(alias="documentNumber", min_length=5, max_length=30)
    address: str = Field(min_length=5, max_length=300)
    email: EmailStr
    phone: str = Field(min_length=6, max_length=30)
    is_minor: bool = Field(default=False, alias="isMinor")
    representative_name: str | None = Field(default=None, alias="representativeName", min_length=3, max_length=150)
    item_type: Literal["product", "service"] = Field(alias="itemType")
    amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    description: str = Field(min_length=10, max_length=5000)
    requested_action: str = Field(alias="requestedAction", min_length=5, max_length=3000)
    privacy_accepted: bool = Field(alias="privacyAccepted")
    source_url: str | None = Field(default=None, alias="sourceUrl", max_length=500)
    company_website: str | None = Field(default=None, alias="companyWebsite", max_length=200)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        has_plus = value.startswith("+")
        digits = re.sub(r"\D", "", value)
        if not 7 <= len(digits) <= 15:
            raise ValueError("el telefono debe contener entre 7 y 15 digitos")
        return f"+{digits}" if has_plus else digits

    @model_validator(mode="after")
    def validate_controls(self) -> "ComplaintCreate":
        if not self.privacy_accepted:
            raise ValueError("debe aceptar la politica de privacidad")
        if self.company_website:
            raise ValueError("solicitud no valida")
        if self.is_minor and not self.representative_name:
            raise ValueError("representativeName es obligatorio para menores")
        return self

    def persistence_data(self) -> dict:
        return self.model_dump(exclude={"company_website"})


class ComplaintCreated(BaseModel):
    success: bool = True
    complaint_id: int = Field(alias="complaintId")

    model_config = ConfigDict(populate_by_name=True)
