from __future__ import annotations

import argparse

from app.services.notifications import process_notifications
from app.brands import get_brand_registry


def retry_failed_emails(lead_id: int | None = None, limit: int = 50) -> int:
    get_brand_registry()  # Validate SMTP profiles before claiming jobs.
    return process_notifications(limit=limit, lead_id=lead_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reintenta una vez los correos pendientes o fallidos")
    parser.add_argument("--lead-id", type=int)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    processed = retry_failed_emails(args.lead_id, max(1, min(args.limit, 100)))
    print(f"Notificaciones procesadas: {processed}")
