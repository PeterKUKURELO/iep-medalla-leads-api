from __future__ import annotations

from typing import Literal

BelsitecClassification = Literal["prioritario", "evaluacion", "informativo"]

DECISION_ROLES = ("director", "gerente", "rector", "promotor", "propietario", "coordinador")
PUBLIC_EMAIL_DOMAINS = {"gmail.com", "hotmail.com", "outlook.com", "yahoo.com"}


def classify_belsitec_lead(job_title: str | None, email: str, organization_name: str | None) -> BelsitecClassification:
    normalized_role = (job_title or "").casefold()
    domain = email.rsplit("@", 1)[-1].casefold()
    has_organization = bool(organization_name and organization_name.strip())
    is_decision_role = any(role in normalized_role for role in DECISION_ROLES)
    is_corporate_email = domain not in PUBLIC_EMAIL_DOMAINS
    if has_organization and is_decision_role and is_corporate_email:
        return "prioritario"
    if has_organization or is_decision_role:
        return "evaluacion"
    return "informativo"
