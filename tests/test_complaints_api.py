from app.database import SessionLocal
from app.models import Complaint, Lead


COMPLAINT = {
    "complaintType": "claim",
    "fullName": "Persona Consumidora",
    "documentType": "dni",
    "documentNumber": "12345678",
    "address": "Av. Ejemplo 123, Lima",
    "email": "consumer@example.com",
    "phone": "999 999 999",
    "itemType": "service",
    "amount": "120.50",
    "description": "Descripción detallada del servicio reclamado.",
    "requestedAction": "Solicito una respuesta por escrito.",
    "privacyAccepted": True,
}


def test_complaint_is_stored_outside_leads(client):
    response = client.post("/api/v1/complaints", json=COMPLAINT)
    assert response.status_code == 201
    with SessionLocal() as db:
        complaint = db.get(Complaint, response.json()["complaintId"])
        assert complaint.document_number == "12345678"
        assert complaint.phone == "999999999"
        assert db.query(Lead).count() == 0


def test_minor_requires_representative_and_honeypot_is_rejected(client):
    assert client.post("/api/v1/complaints", json={**COMPLAINT, "isMinor": True}).status_code == 422
    assert client.post("/api/v1/complaints", json={**COMPLAINT, "companyWebsite": "spam"}).status_code == 422


def test_request_id_is_validated_and_returned(client):
    supplied = client.get("/health", headers={"X-Request-ID": "request-123"})
    assert supplied.headers["X-Request-ID"] == "request-123"
    replaced = client.get("/health", headers={"X-Request-ID": "contains pii@example.com"})
    assert replaced.headers["X-Request-ID"] != "contains pii@example.com"
    assert len(replaced.headers["X-Request-ID"]) == 36
