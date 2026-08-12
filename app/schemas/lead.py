from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

GRADES_BY_LEVEL = {
    "Inicial": {"3 años", "4 años", "5 años"},
    "Primaria": {f"{number}° grado" for number in range(1, 7)},
}


class LeadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    form_type: Literal["admission", "contact"] = Field(alias="formType")
    full_name: str = Field(alias="fullName", min_length=3, max_length=150)
    phone: str = Field(min_length=6, max_length=30)
    email: EmailStr
    privacy_accepted: bool = Field(alias="privacyAccepted")
    education_level: str | None = Field(default=None, alias="educationLevel", max_length=50)
    grade: str | None = Field(default=None, max_length=50)
    contact_reason: str | None = Field(default=None, alias="contactReason", max_length=150)
    message: str | None = Field(default=None, min_length=5, max_length=2000)
    source_url: str | None = Field(default=None, alias="sourceUrl", max_length=500)
    utm_source: str | None = Field(default=None, alias="utmSource", max_length=100)
    utm_medium: str | None = Field(default=None, alias="utmMedium", max_length=100)
    utm_campaign: str | None = Field(default=None, alias="utmCampaign", max_length=150)
    company_website: str | None = Field(default=None, alias="companyWebsite", max_length=200)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        value = value.strip()
        has_plus = value.startswith("+")
        digits = re.sub(r"\D", "", value)
        if not 7 <= len(digits) <= 15:
            raise ValueError("el telefono debe contener entre 7 y 15 digitos")
        return f"+{digits}" if has_plus else digits

    @model_validator(mode="after")
    def validate_form_fields(self) -> "LeadCreate":
        if not self.privacy_accepted:
            raise ValueError("debe aceptar la politica de privacidad")
        if self.company_website:
            raise ValueError("solicitud no valida")
        if self.form_type == "admission":
            if not self.education_level or not self.grade:
                raise ValueError("educationLevel y grade son obligatorios para admission")
            allowed_grades = GRADES_BY_LEVEL.get(self.education_level)
            if not allowed_grades or self.grade not in allowed_grades:
                raise ValueError("el grado no corresponde al nivel seleccionado")
            if self.contact_reason is not None or self.message is not None:
                raise ValueError("contactReason y message no corresponden a admission")
        else:
            if not self.contact_reason or not self.message:
                raise ValueError("contactReason y message son obligatorios para contact")
            if self.education_level is not None or self.grade is not None:
                raise ValueError("educationLevel y grade no corresponden a contact")
        return self

    def persistence_data(self) -> dict[str, object]:
        return self.model_dump(exclude={"company_website"})


class LeadCreated(BaseModel):
    success: bool = True
    message: str = "Recibimos tus datos correctamente."
    lead_id: int = Field(alias="leadId")

    model_config = ConfigDict(populate_by_name=True)
