from __future__ import annotations

import logging

from app.config import get_settings
from app.database import SessionLocal
from app.repositories.leads import get_lead, update_email_status
from app.services.email import EmailService

logger = logging.getLogger(__name__)


def deliver_lead_notifications(lead_id: int) -> None:
    """Background task. It owns its DB session; request sessions are already closed."""
    with SessionLocal() as db:
        lead = get_lead(db, lead_id)
        if lead is None:
            logger.error("notification_lead_not_found", extra={"lead_id": lead_id})
            return

        service = EmailService(get_settings())
        deliveries = (
            ("admin", service.send_admin_notification),
            ("user", service.send_user_confirmation),
        )
        for kind, sender in deliveries:
            if getattr(lead, f"{kind}_email_status") == "sent":
                continue
            try:
                sender(lead)
                update_email_status(db, lead, kind, "sent")
            except Exception as exc:
                db.rollback()
                update_email_status(db, lead, kind, "failed", type(exc).__name__ + ": " + str(exc))
                logger.warning(
                    "email_delivery_failed",
                    extra={"lead_id": lead_id, "email_kind": kind, "error_type": type(exc).__name__},
                )
