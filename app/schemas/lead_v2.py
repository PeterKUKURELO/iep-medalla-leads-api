from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.domain.leads import CreateLeadCommand


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)


class LeadData(StrictModel):
    pass


class AdmissionData(LeadData):
    education_level: Literal["Inicial", "Primaria"] = Field(alias="educationLevel")
    grade: str = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def grade_matches_level(self) -> "AdmissionData":
        from app.schemas.lead import GRADES_BY_LEVEL

        if self.grade not in GRADES_BY_LEVEL[self.education_level]:
            raise ValueError("el grado no corresponde al nivel seleccionado")
        return self


class ContactData(LeadData):
    contact_reason: str = Field(alias="contactReason", min_length=1, max_length=150)


class BelsitecMeetingData(LeadData):
    contact_description: str | None = Field(default=None, alias="contactDescription", min_length=5, max_length=2000)


class MieduDemoData(LeadData):
    student_range: str = Field(alias="studentRange", min_length=1, max_length=50)
    primary_need: str = Field(alias="primaryNeed", min_length=1, max_length=100)


class MieduSalesData(LeadData):
    city: str | None = Field(default=None, min_length=1, max_length=100)
    schedule: str | None = Field(default=None, min_length=1, max_length=100)
    primary_need: str | None = Field(default=None, alias="primaryNeed", min_length=1, max_length=100)


class LeadV2Base(StrictModel):
    brand: str
    form_type: str = Field(alias="formType")
    source_key: str | None = Field(default=None, alias="sourceKey", max_length=100)
    full_name: str = Field(alias="fullName", min_length=3, max_length=150)
    email: EmailStr
    phone_country: str | None = Field(default=None, alias="phoneCountry", min_length=2, max_length=2)
    phone: str = Field(min_length=6, max_length=30)
    organization_name: str | None = Field(default=None, alias="organizationName", max_length=200)
    job_title: str | None = Field(default=None, alias="jobTitle", max_length=120)
    message: str | None = Field(default=None, min_length=5, max_length=2000)
    privacy_accepted: bool = Field(alias="privacyAccepted")
    source_url: str | None = Field(default=None, alias="sourceUrl", max_length=500)
    utm_source: str | None = Field(default=None, alias="utmSource", max_length=100)
    utm_medium: str | None = Field(default=None, alias="utmMedium", max_length=100)
    utm_campaign: str | None = Field(default=None, alias="utmCampaign", max_length=150)
    utm_content: str | None = Field(default=None, alias="utmContent", max_length=150)
    utm_term: str | None = Field(default=None, alias="utmTerm", max_length=150)
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

    @field_validator("phone_country")
    @classmethod
    def normalize_country(cls, value: str | None) -> str | None:
        return value.upper() if value else None

    @model_validator(mode="after")
    def validate_public_controls(self) -> "LeadV2Base":
        if not self.privacy_accepted:
            raise ValueError("debe aceptar la politica de privacidad")
        if self.company_website:
            raise ValueError("solicitud no valida")
        return self

    def to_command(self) -> CreateLeadCommand:
        data = self.data.model_dump(by_alias=True, exclude_none=True)
        message = self.message
        if isinstance(self.data, BelsitecMeetingData) and self.data.contact_description and not message:
            message = self.data.contact_description
        return CreateLeadCommand(
            brand_key=self.brand,
            form_type=self.form_type,
            source_key=self.source_key,
            full_name=self.full_name,
            email=str(self.email),
            phone_country=self.phone_country,
            phone=self.phone,
            organization_name=self.organization_name,
            job_title=self.job_title,
            message=message,
            privacy_accepted=self.privacy_accepted,
            form_data=data,
            source_url=self.source_url,
            utm_source=self.utm_source,
            utm_medium=self.utm_medium,
            utm_campaign=self.utm_campaign,
            utm_content=self.utm_content,
            utm_term=self.utm_term,
            education_level=self.data.education_level if isinstance(self.data, AdmissionData) else None,
            grade=self.data.grade if isinstance(self.data, AdmissionData) else None,
            contact_reason=self.data.contact_reason if isinstance(self.data, ContactData) else None,
        )


class MedallaAdmissionLead(LeadV2Base):
    brand: Literal["iep-medalla"]
    form_type: Literal["admission"] = Field(alias="formType")
    data: AdmissionData


class MedallaContactLead(LeadV2Base):
    brand: Literal["iep-medalla"]
    form_type: Literal["contact"] = Field(alias="formType")
    data: ContactData


class BelsitecMeetingLead(LeadV2Base):
    brand: Literal["belsitec"]
    form_type: Literal["meeting_request"] = Field(alias="formType")
    organization_name: str = Field(alias="organizationName", min_length=2, max_length=200)
    job_title: str = Field(alias="jobTitle", min_length=2, max_length=120)
    data: BelsitecMeetingData = Field(default_factory=BelsitecMeetingData)

    @model_validator(mode="before")
    @classmethod
    def accept_current_belsitec_names(cls, value):
        if not isinstance(value, dict):
            return value
        mapped = dict(value)
        aliases = {
            "nombre": "fullName",
            "cargo": "jobTitle",
            "institucion": "organizationName",
            "telefono": "phone",
        }
        for source, target in aliases.items():
            if source in mapped and target not in mapped:
                mapped[target] = mapped.pop(source)
        if "descripcion" in mapped:
            data = dict(mapped.get("data") or {})
            data.setdefault("contactDescription", mapped.pop("descripcion"))
            mapped["data"] = data
        return mapped


class MieduDemoLead(LeadV2Base):
    brand: Literal["miedu-pe"]
    form_type: Literal["demo_request"] = Field(alias="formType")
    phone_country: str = Field(alias="phoneCountry", min_length=2, max_length=2)
    organization_name: str = Field(alias="organizationName", min_length=2, max_length=200)
    job_title: str = Field(alias="jobTitle", min_length=2, max_length=120)
    data: MieduDemoData

    @model_validator(mode="before")
    @classmethod
    def accept_current_miedu_names(cls, value):
        return _map_miedu_flat_payload(value)


class MieduSalesContactLead(LeadV2Base):
    brand: Literal["miedu-pe"]
    form_type: Literal["sales_contact"] = Field(alias="formType")
    phone_country: str = Field(alias="phoneCountry", min_length=2, max_length=2)
    organization_name: str = Field(alias="organizationName", min_length=2, max_length=200)
    job_title: str = Field(alias="jobTitle", min_length=2, max_length=120)
    data: MieduSalesData

    @model_validator(mode="before")
    @classmethod
    def accept_current_miedu_names(cls, value):
        return _map_miedu_flat_payload(value)


def _map_miedu_flat_payload(value):
    if not isinstance(value, dict):
        return value
    mapped = dict(value)
    aliases = {
        "name": "fullName",
        "school": "organizationName",
        "role": "jobTitle",
        "privacy": "privacyAccepted",
    }
    for source, target in aliases.items():
        if source in mapped and target not in mapped:
            mapped[target] = mapped.pop(source)
    data = dict(mapped.get("data") or {})
    for source, target in (("students", "studentRange"), ("need", "primaryNeed"), ("city", "city"), ("schedule", "schedule")):
        if source in mapped:
            data.setdefault(target, mapped.pop(source))
    if data:
        mapped["data"] = data
    return mapped


LeadV2Payload = Annotated[
    MedallaAdmissionLead | MedallaContactLead | BelsitecMeetingLead | MieduDemoLead | MieduSalesContactLead,
    Field(discriminator="form_type"),
]
