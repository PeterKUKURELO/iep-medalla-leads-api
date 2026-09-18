from __future__ import annotations

from sqlalchemy.orm import Session

from app.brands import BrandConfig, BrandRegistry
from app.domain.leads import CreateLeadCommand
from app.models.lead import Lead
from app.models.notification import LeadNotification
from app.repositories.leads import add_lead


class FormNotAllowedError(ValueError):
    pass


class OriginNotAllowedError(ValueError):
    pass


class LeadService:
    def __init__(self, registry: BrandRegistry) -> None:
        self.registry = registry

    def create(self, db: Session, command: CreateLeadCommand, origin: str | None = None) -> Lead:
        brand = self.registry.require(command.brand_key)
        self._validate_policy(brand, command.form_type, origin)
        try:
            lead = add_lead(db, command)
            db.add_all(
                [
                    LeadNotification(lead_id=lead.id, kind=kind,
                                     status="pending" if brand.notifications_enabled else "disabled",
                                     last_error_code=None if brand.notifications_enabled else "brand_notifications_disabled")
                    for kind in ("admin", "user")
                ]
            )
            db.commit()
            db.refresh(lead)
            return lead
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _validate_policy(brand: BrandConfig, form_type: str, origin: str | None) -> None:
        if form_type not in brand.allowed_forms:
            raise FormNotAllowedError(form_type)
        if origin is not None and origin not in brand.allowed_origins:
            raise OriginNotAllowedError(origin)
