import pytest

from app.brands import get_brand_registry
from app.database import SessionLocal
from app.models import Lead, LeadNotification


BASE = {
    "sourceKey": "hero_demo",
    "fullName": "María García",
    "email": "direccion@example.com",
    "phone": "999 999 999",
    "privacyAccepted": True,
    "sourceUrl": "/",
}


@pytest.fixture(autouse=True)
def enable_new_brands_for_contract_tests():
    brands = [get_brand_registry().get(key) for key in ("iep-medalla", "belsitec", "miedu-pe")]
    originals = [(brand.enabled, set(brand.allowed_origins)) for brand in brands]
    for brand in brands:
        brand.enabled = True
        brand.allowed_origins = {*brand.allowed_origins, "http://localhost:8443"}
    yield
    for brand, original in zip(brands, originals, strict=True):
        brand.enabled, brand.allowed_origins = original


def _post(client, payload, origin="http://localhost:8443"):
    return client.post("/api/v2/leads", json=payload, headers={"Origin": origin})


def _assert_created(response, brand, form_type):
    assert response.status_code == 201, response.text
    with SessionLocal() as db:
        lead = db.get(Lead, response.json()["leadId"])
        assert lead.brand_key == brand
        assert lead.form_type == form_type
        assert len(db.query(LeadNotification).filter_by(lead_id=lead.id).all()) == 2
        return lead.id


def test_v2_medalla_admission(client):
    response = _post(client, {**BASE, "brand": "iep-medalla", "formType": "admission", "data": {"educationLevel": "Inicial", "grade": "4 años"}})
    lead_id = _assert_created(response, "iep-medalla", "admission")
    with SessionLocal() as db:
        assert db.get(Lead, lead_id).form_data == {"educationLevel": "Inicial", "grade": "4 años"}


def test_v2_medalla_contact(client):
    response = _post(client, {**BASE, "brand": "iep-medalla", "formType": "contact", "message": "Necesito información.", "data": {"contactReason": "Matrícula"}})
    _assert_created(response, "iep-medalla", "contact")


def test_v2_belsitec_meeting_is_classified_by_backend(client):
    response = _post(client, {**BASE, "brand": "belsitec", "formType": "meeting_request", "organizationName": "Colegio Ejemplo", "jobTitle": "Directora", "data": {"contactDescription": "Solicito una reunión comercial."}})
    lead_id = _assert_created(response, "belsitec", "meeting_request")
    with SessionLocal() as db:
        lead = db.get(Lead, lead_id)
        assert lead.classification == "prioritario"
        assert lead.message == "Solicito una reunión comercial."
        assert lead.device_type == "desktop"


def test_v2_miedu_demo(client):
    response = _post(client, {**BASE, "brand": "miedu-pe", "formType": "demo_request", "phoneCountry": "pe", "organizationName": "Colegio Ejemplo", "jobTitle": "Directora", "data": {"studentRange": "201–500", "primaryNeed": "Admisión"}})
    lead_id = _assert_created(response, "miedu-pe", "demo_request")
    with SessionLocal() as db:
        assert db.get(Lead, lead_id).phone_country == "PE"


def test_v2_miedu_sales_contact(client):
    response = _post(client, {**BASE, "brand": "miedu-pe", "formType": "sales_contact", "phoneCountry": "PE", "organizationName": "Colegio Ejemplo", "jobTitle": "Administradora", "data": {"city": "Lima", "schedule": "Mañana"}})
    _assert_created(response, "miedu-pe", "sales_contact")


def test_v2_accepts_current_frontend_field_names(client):
    belsitec = _post(client, {"brand": "belsitec", "formType": "meeting_request", "sourceKey": "contact_section", "nombre": "Ana Pérez", "cargo": "Directora", "institucion": "Colegio Uno", "telefono": "999999999", "email": "ana@example.com", "privacyAccepted": True, "descripcion": "Quiero coordinar una reunión."})
    _assert_created(belsitec, "belsitec", "meeting_request")

    miedu = _post(client, {"brand": "miedu-pe", "formType": "demo_request", "sourceKey": "footer_demo", "name": "Luis Pérez", "school": "Colegio Dos", "phoneCountry": "PE", "phone": "988888888", "students": "201–500", "email": "luis@example.com", "role": "Director", "need": "Admisión", "privacy": True})
    _assert_created(miedu, "miedu-pe", "demo_request")


def test_v2_security_rejections(client):
    valid = {**BASE, "brand": "belsitec", "formType": "meeting_request", "organizationName": "Colegio", "jobTitle": "Director", "data": {}}
    assert _post(client, valid, origin="https://evil.example").status_code == 403
    assert _post(client, {**valid, "classification": "prioritario"}).status_code == 422
    assert _post(client, {**valid, "companyWebsite": "spam.example"}).status_code == 422
    assert _post(client, {**valid, "brand": "unknown"}).status_code == 422


def test_v2_disabled_brand(client):
    brand = get_brand_registry().get("belsitec")
    original = brand.enabled
    brand.enabled = False
    try:
        payload = {**BASE, "brand": "belsitec", "formType": "meeting_request", "organizationName": "Colegio", "jobTitle": "Director", "data": {}}
        assert _post(client, payload).status_code == 403
    finally:
        brand.enabled = original
