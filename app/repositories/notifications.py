from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.models.notification import LeadNotification


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True, slots=True)
class ClaimedNotification:
    id: int
    claim_token: str


def claim_due_notifications(
    db: Session,
    *,
    limit: int,
    lease_seconds: int,
    lead_id: int | None = None,
) -> list[ClaimedNotification]:
    now = utcnow()
    eligible = or_(
        and_(LeadNotification.status.in_(("pending", "failed")), or_(LeadNotification.next_attempt_at.is_(None), LeadNotification.next_attempt_at <= now)),
        and_(LeadNotification.status == "processing", LeadNotification.locked_until <= now),
    )
    query = select(LeadNotification.id).where(eligible).order_by(LeadNotification.id).limit(limit)
    if lead_id is not None:
        query = query.where(LeadNotification.lead_id == lead_id)
    candidates = list(db.scalars(query))
    claimed: list[ClaimedNotification] = []
    for notification_id in candidates:
        token = str(uuid4())
        result = db.execute(
            update(LeadNotification)
            .where(LeadNotification.id == notification_id, eligible)
            .values(
                status="processing",
                claim_token=token,
                locked_until=now + timedelta(seconds=lease_seconds),
                attempt_count=LeadNotification.attempt_count + 1,
            )
        )
        if result.rowcount == 1:
            claimed.append(ClaimedNotification(notification_id, token))
    db.commit()
    return claimed


def finish_notification(
    db: Session,
    claimed: ClaimedNotification,
    *,
    status: str,
    error_code: str | None = None,
    next_attempt_at: datetime | None = None,
    commit: bool = True,
) -> bool:
    values = {
        "status": status,
        "claim_token": None,
        "locked_until": None,
        "last_error_code": error_code,
        "next_attempt_at": next_attempt_at,
    }
    if status == "sent":
        values["sent_at"] = utcnow()
    result = db.execute(
        update(LeadNotification)
        .where(
            LeadNotification.id == claimed.id,
            LeadNotification.status == "processing",
            LeadNotification.claim_token == claimed.claim_token,
        )
        .values(**values)
    )
    if commit:
        db.commit()
    return result.rowcount == 1
