from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.domain.leads import CreateLeadCommand

EmailKind = Literal["admin", "user"]
EmailStatus = Literal["pending", "sent", "failed"]


def add_lead(db: Session, command: CreateLeadCommand) -> Lead:
    lead = Lead(**command.as_persistence_data())
    db.add(lead)
    db.flush()
    return lead


def create_lead(db: Session, command: CreateLeadCommand) -> Lead:
    """Compatibility wrapper. New services should own the transaction."""
    lead = add_lead(db, command)
    try:
        db.commit()
        db.refresh(lead)
    except Exception:
        db.rollback()
        raise
    return lead


def get_lead(db: Session, lead_id: int) -> Lead | None:
    return db.get(Lead, lead_id)


def update_email_status(
    db: Session,
    lead: Lead,
    kind: EmailKind,
    status: EmailStatus,
    error: str | None = None,
) -> None:
    setattr(lead, f"{kind}_email_status", status)
    if status == "sent":
        setattr(lead, f"{kind}_email_sent_at", datetime.now(timezone.utc).replace(tzinfo=None))
    if error:
        safe_error = " ".join(error.split())[:400]
        prefix = f"{kind}: "
        previous = f"{lead.email_error}; " if lead.email_error else ""
        lead.email_error = f"{previous}{prefix}{safe_error}"[:500]
    db.commit()
