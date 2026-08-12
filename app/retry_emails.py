from __future__ import annotations

import argparse

from sqlalchemy import or_, select

from app.database import SessionLocal
from app.models.lead import Lead
from app.services.leads import deliver_lead_notifications


def retry_failed_emails(lead_id: int | None = None, limit: int = 50) -> int:
    with SessionLocal() as db:
        query = select(Lead.id).where(
            or_(Lead.admin_email_status.in_(["pending", "failed"]), Lead.user_email_status.in_(["pending", "failed"]))
        )
        if lead_id is not None:
            query = query.where(Lead.id == lead_id)
        ids = list(db.scalars(query.order_by(Lead.id).limit(limit)))

    for current_id in ids:
        deliver_lead_notifications(current_id)
    return len(ids)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reintenta una vez los correos pendientes o fallidos")
    parser.add_argument("--lead-id", type=int)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    processed = retry_failed_emails(args.lead_id, max(1, min(args.limit, 100)))
    print(f"Leads procesados: {processed}")
