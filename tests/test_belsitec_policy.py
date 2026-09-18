from app.policies.belsitec import classify_belsitec_lead


def test_belsitec_classification_policy():
    assert classify_belsitec_lead("Directora", "maria@colegio.edu.pe", "Colegio") == "prioritario"
    assert classify_belsitec_lead("Asistente", "maria@gmail.com", "Colegio") == "evaluacion"
    assert classify_belsitec_lead(None, "maria@gmail.com", None) == "informativo"
