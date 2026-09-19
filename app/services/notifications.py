from __future__ import annotations

import logging
import smtplib
from datetime import timedelta

from app.config import get_settings
from app.brands import get_brand_registry
from app.database import SessionLocal
from app.models.lead import Lead
from app.models.notification import LeadNotification
from app.repositories.notifications import ClaimedNotification, claim_due_notifications, finish_notification, utcnow
from app.services.email import EmailService

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 5
LEASE_SECONDS = 60

PERMANENT_SMTP_ERRORS = (
    smtplib.SMTPAuthenticationError,
    smtplib.SMTPRecipientsRefused,
    smtplib.SMTPSenderRefused,
    smtplib.SMTPNotSupportedError,
)


def process_notifications(limit: int = 50, lead_id: int | None = None, email_service_class=EmailService) -> int:
    with SessionLocal() as db:
        claimed_jobs = claim_due_notifications(db, limit=limit, lease_seconds=LEASE_SECONDS, lead_id=lead_id)
    for claimed in claimed_jobs:
        _deliver_claimed(claimed, email_service_class)
    return len(claimed_jobs)


def _deliver_claimed(claimed: ClaimedNotification, email_service_class=EmailService) -> None:
    with SessionLocal() as db:
        notification = db.get(LeadNotification, claimed.id)
        if notification is None or notification.claim_token != claimed.claim_token:
            return
        lead = db.get(Lead, notification.lead_id)
        if lead is None:
            finish_notification(db, claimed, status="dead", error_code="lead_not_found")
            return
        kind = notification.kind
        attempt_count = notification.attempt_count

    settings = get_settings()
    if not settings.mail_enabled and email_service_class is EmailService:
        _finalize(claimed, lead.id, kind, "disabled", "smtp_disabled")
        return

    try:
        brand = get_brand_registry().require(lead.brand_key)
        if not brand.notifications_enabled:
            _finalize(claimed, lead.id, kind, "disabled", "brand_notifications_disabled")
            return
        service = email_service_class(settings)
        if kind == "admin":
            service.send_admin_notification(lead)
        else:
            service.send_user_confirmation(lead)
    except PERMANENT_SMTP_ERRORS as exc:
        _finalize(claimed, lead.id, kind, "dead", type(exc).__name__)
    except Exception as exc:
        if attempt_count >= MAX_ATTEMPTS:
            _finalize(claimed, lead.id, kind, "dead", type(exc).__name__)
        else:
            delay = timedelta(minutes=2 ** max(0, attempt_count - 1))
            _finalize(claimed, lead.id, kind, "failed", type(exc).__name__, utcnow() + delay)
        logger.warning(
            "email_delivery_failed",
            extra={"lead_id": lead.id, "email_kind": kind, "error_type": type(exc).__name__},
        )
    else:
        _finalize(claimed, lead.id, kind, "sent")


def _finalize(
    claimed: ClaimedNotification,
    lead_id: int,
    kind: str,
    status: str,
    error_code: str | None = None,
    next_attempt_at=None,
) -> None:
    with SessionLocal() as db:
        if not finish_notification(
            db,
            claimed,
            status=status,
            error_code=error_code,
            next_attempt_at=next_attempt_at,
            commit=False,
        ):
            db.rollback()
            return
        lead = db.get(Lead, lead_id)
        if lead is None:
            db.commit()
            return
        # Legacy columns remain a compatibility projection during coexistence.
        legacy_status = "sent" if status == "sent" else "failed"
        setattr(lead, f"{kind}_email_status", legacy_status)
        if status == "sent":
            notification = db.get(LeadNotification, claimed.id)
            setattr(lead, f"{kind}_email_sent_at", notification.sent_at)
        if error_code:
            lead.email_error = f"{kind}: {error_code}"[:500]
        db.commit()
