import smtplib
import pytest
from datetime import timedelta

from app.database import SessionLocal
from app.models import Lead, LeadNotification
from app.repositories.notifications import claim_due_notifications, utcnow
from app.services.notifications import MAX_ATTEMPTS, process_notifications


def _job(kind="admin", brand_key="iep-medalla"):
    with SessionLocal() as db:
        lead = Lead(
            brand_key=brand_key,
            form_type="contact",
            full_name="Persona de Prueba",
            phone="999999999",
            email="person@example.com",
            contact_reason="Información",
            message="Mensaje de prueba",
            privacy_accepted=True,
            form_data={"contactReason": "Información"},
        )
        db.add(lead)
        db.flush()
        notification = LeadNotification(lead_id=lead.id, kind=kind)
        db.add(notification)
        db.commit()
        return notification.id


class SuccessEmailService:
    def __init__(self, settings):
        pass

    def send_admin_notification(self, lead):
        return None

    def send_user_confirmation(self, lead):
        return None


def test_notification_success():
    notification_id = _job()
    assert process_notifications(email_service_class=SuccessEmailService) == 1
    with SessionLocal() as db:
        job = db.get(LeadNotification, notification_id)
        assert job.status == "sent"
        assert job.sent_at is not None
        assert job.attempt_count == 1


def test_temporary_error_is_retried_after_due_time():
    notification_id = _job()

    class TemporaryFailure(SuccessEmailService):
        def send_admin_notification(self, lead):
            raise TimeoutError("temporary")

    process_notifications(email_service_class=TemporaryFailure)
    with SessionLocal() as db:
        job = db.get(LeadNotification, notification_id)
        assert job.status == "failed"
        assert job.last_error_code == "TimeoutError"
        assert job.next_attempt_at > utcnow()
        job.next_attempt_at = utcnow() - timedelta(seconds=1)
        db.commit()

    process_notifications(email_service_class=SuccessEmailService)
    with SessionLocal() as db:
        assert db.get(LeadNotification, notification_id).status == "sent"


def test_permanent_error_goes_dead_without_retry():
    notification_id = _job()

    class PermanentFailure(SuccessEmailService):
        def send_admin_notification(self, lead):
            raise smtplib.SMTPRecipientsRefused({"x@example.com": (550, b"rejected")})

    process_notifications(email_service_class=PermanentFailure)
    with SessionLocal() as db:
        assert db.get(LeadNotification, notification_id).status == "dead"
    assert process_notifications(email_service_class=SuccessEmailService) == 0


def test_max_retry_goes_dead():
    notification_id = _job()
    with SessionLocal() as db:
        job = db.get(LeadNotification, notification_id)
        job.attempt_count = MAX_ATTEMPTS - 1
        db.commit()

    class TemporaryFailure(SuccessEmailService):
        def send_admin_notification(self, lead):
            raise TimeoutError("temporary")

    process_notifications(email_service_class=TemporaryFailure)
    with SessionLocal() as db:
        job = db.get(LeadNotification, notification_id)
        assert job.status == "dead"
        assert job.attempt_count == MAX_ATTEMPTS


def test_two_workers_cannot_claim_same_job():
    notification_id = _job()
    with SessionLocal() as first, SessionLocal() as second:
        first_claim = claim_due_notifications(first, limit=1, lease_seconds=60)
        second_claim = claim_due_notifications(second, limit=1, lease_seconds=60)
    assert [item.id for item in first_claim] == [notification_id]
    assert second_claim == []


def test_expired_processing_job_is_recovered_after_restart():
    notification_id = _job()
    with SessionLocal() as db:
        job = db.get(LeadNotification, notification_id)
        job.status = "processing"
        job.claim_token = "abandoned"
        job.locked_until = utcnow() - timedelta(seconds=1)
        db.commit()

    assert process_notifications(email_service_class=SuccessEmailService) == 1
    with SessionLocal() as db:
        assert db.get(LeadNotification, notification_id).status == "sent"


@pytest.mark.parametrize("kind", ["admin", "user"])
@pytest.mark.parametrize("status", ["pending", "failed", "processing"])
def test_existing_disabled_brand_jobs_never_send_or_retry(monkeypatch, kind, status):
    from app.brands import get_brand_registry
    brand = get_brand_registry().get("miedu-pe")
    monkeypatch.setattr(brand, "notifications_enabled", False)
    notification_id = _job(kind, "miedu-pe")
    with SessionLocal() as db:
        job = db.get(LeadNotification, notification_id)
        job.status = status
        job.next_attempt_at = utcnow() - timedelta(seconds=1)
        job.locked_until = utcnow() - timedelta(seconds=1)
        db.commit()

    class MustNotSend:
        def __init__(self, settings):
            raise AssertionError("Disabled brand must not construct SMTP service")

    assert process_notifications(email_service_class=MustNotSend) == 1
    with SessionLocal() as db:
        job = db.get(LeadNotification, notification_id)
        assert job.status == "disabled"
        assert job.last_error_code == "brand_notifications_disabled"
        assert job.sent_at is None
        assert job.next_attempt_at is None
        assert job.claim_token is None
    assert process_notifications(email_service_class=MustNotSend) == 0


def test_disabled_brand_still_persists_lead_and_disabled_jobs(monkeypatch):
    from app.brands import get_brand_registry
    from app.domain.leads import CreateLeadCommand
    from app.services.lead_creation import LeadService
    registry = get_brand_registry()
    monkeypatch.setattr(registry.get("miedu-pe"), "notifications_enabled", False)
    with SessionLocal() as db:
        lead = LeadService(registry).create(db, CreateLeadCommand(
            brand_key="miedu-pe", form_type="demo_request", full_name="Test",
            email="test@example.com", phone="999999999", privacy_accepted=True,
        ))
        jobs = db.query(LeadNotification).filter_by(lead_id=lead.id).all()
        assert len(jobs) == 2
        assert all(job.status == "disabled" and job.attempt_count == 0 for job in jobs)
    assert process_notifications(email_service_class=SuccessEmailService) == 0
    _job(brand_key="iep-medalla")
    assert process_notifications(email_service_class=SuccessEmailService) == 1
