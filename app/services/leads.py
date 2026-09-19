from __future__ import annotations

import logging

from app.services.notifications import process_notifications
from app.services.email import EmailService
from app.database import SessionLocal
from app.models.lead import Lead
from app.models.notification import LeadNotification
from sqlalchemy import select

logger = logging.getLogger(__name__)


def deliver_lead_notifications(lead_id: int) -> None:
    """Compatibility entry point backed by durable notification rows."""
    with SessionLocal() as db:
        if db.get(Lead, lead_id) is None:
            logger.error("notification_lead_not_found", extra={"lead_id": lead_id})
            return
        existing = set(db.scalars(select(LeadNotification.kind).where(LeadNotification.lead_id == lead_id)))
        db.add_all(LeadNotification(lead_id=lead_id, kind=kind) for kind in {"admin", "user"} - existing)
        db.commit()
    process_notifications(limit=2, lead_id=lead_id, email_service_class=EmailService)
