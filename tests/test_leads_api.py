from app.database import SessionLocal
from app.models import Lead
from sqlalchemy.exc import OperationalError


ADMISSION = {
    "formType": "admission",
    "fullName": "María López Torres",
    "phone": "+51 999-999-999",
    "email": "MARIA@example.com",
    "educationLevel": "Inicial",
    "grade": "4 años",
    "privacyAccepted": True,
    "sourceUrl": "/admision",
}


def test_creates_admission_lead_before_email_delivery(client):
    response = client.post("/api/v1/leads", json=ADMISSION)
    assert response.status_code == 201
    assert response.json()["success"] is True

    with SessionLocal() as db:
        lead = db.get(Lead, response.json()["leadId"])
        assert lead is not None
        assert lead.phone == "+51999999999"
        assert lead.email == "maria@example.com"
        # SMTP is intentionally disabled in the automatic test environment.
        assert lead.admin_email_status == "failed"
        assert lead.user_email_status == "failed"


def test_creates_primary_admission(client):
    payload = {**ADMISSION, "educationLevel": "Primaria", "grade": "6° grado"}
    assert client.post("/api/v1/leads", json=payload).status_code == 201


def test_creates_contact_with_accents(client):
    payload = {
        "formType": "contact",
        "fullName": "Íñigo Núñez",
        "phone": "988 888 888",
        "email": "inigo@example.com",
        "contactReason": "Información académica",
        "message": "Deseo información sobre Primaria y matrícula.",
        "privacyAccepted": True,
        "sourceUrl": "/contacto",
    }
    assert client.post("/api/v1/leads", json=payload).status_code == 201


def test_rejects_invalid_conditional_fields(client):
    missing_grade = {key: value for key, value in ADMISSION.items() if key != "grade"}
    assert client.post("/api/v1/leads", json=missing_grade).status_code == 422

    wrong_grade = {**ADMISSION, "educationLevel": "Inicial", "grade": "1° grado"}
    assert client.post("/api/v1/leads", json=wrong_grade).status_code == 422


def test_rejects_invalid_email_and_privacy(client):
    assert client.post("/api/v1/leads", json={**ADMISSION, "email": "bad"}).status_code == 422
    assert client.post("/api/v1/leads", json={**ADMISSION, "privacyAccepted": False}).status_code == 422


def test_rejects_honeypot_and_unknown_fields(client):
    assert client.post("/api/v1/leads", json={**ADMISSION, "companyWebsite": "spam.test"}).status_code == 422
    assert client.post("/api/v1/leads", json={**ADMISSION, "unexpected": "value"}).status_code == 422


def test_rate_limit(client):
    for index in range(5):
        payload = {**ADMISSION, "email": f"person{index}@example.com"}
        assert client.post("/api/v1/leads", json=payload).status_code == 201
    assert client.post("/api/v1/leads", json=ADMISSION).status_code == 429


def test_cors_only_allows_local_frontend(client):
    allowed = client.options(
        "/api/v1/leads",
        headers={"Origin": "http://localhost:8443", "Access-Control-Request-Method": "POST"},
    )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:8443"
    denied = client.options(
        "/api/v1/leads",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in denied.headers


def test_health_checks_database(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_rejects_large_body(client):
    response = client.post(
        "/api/v1/leads",
        content=b"x" * 20_000,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413


def test_database_failure_returns_generic_error(client, monkeypatch):
    def fail_create(*args, **kwargs):
        raise OperationalError("INSERT", {}, RuntimeError("secret database detail"))

    monkeypatch.setattr("app.routers.leads.create_lead", fail_create)
    response = client.post("/api/v1/leads", json=ADMISSION)
    assert response.status_code == 500
    assert response.json() == {"detail": "No fue posible guardar tus datos."}
    assert "secret" not in response.text
