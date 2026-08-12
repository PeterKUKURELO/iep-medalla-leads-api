from app.database import SessionLocal
from app.models import Lead
from app.services.leads import deliver_lead_notifications


def _lead() -> int:
    with SessionLocal() as db:
        lead = Lead(
            form_type="contact",
            full_name="Persona de Prueba",
            phone="999999999",
            email="person@example.com",
            contact_reason="Información",
            message="Mensaje de prueba",
            privacy_accepted=True,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead.id


def test_admin_failure_does_not_prevent_user_email(monkeypatch):
    lead_id = _lead()

    class PartialFailureEmailService:
        def __init__(self, settings):
            pass

        def send_admin_notification(self, lead):
            raise RuntimeError("sandbox admin failure")

        def send_user_confirmation(self, lead):
            return None

    monkeypatch.setattr("app.services.leads.EmailService", PartialFailureEmailService)
    deliver_lead_notifications(lead_id)

    with SessionLocal() as db:
        lead = db.get(Lead, lead_id)
        assert lead.admin_email_status == "failed"
        assert lead.user_email_status == "sent"
        assert lead.user_email_sent_at is not None


def test_user_failure_keeps_saved_lead_and_admin_success(monkeypatch):
    lead_id = _lead()

    class PartialFailureEmailService:
        def __init__(self, settings):
            pass

        def send_admin_notification(self, lead):
            return None

        def send_user_confirmation(self, lead):
            raise RuntimeError("sandbox user failure")

    monkeypatch.setattr("app.services.leads.EmailService", PartialFailureEmailService)
    deliver_lead_notifications(lead_id)

    with SessionLocal() as db:
        lead = db.get(Lead, lead_id)
        assert lead is not None
        assert lead.admin_email_status == "sent"
        assert lead.user_email_status == "failed"
