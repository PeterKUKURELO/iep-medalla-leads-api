from __future__ import annotations

from dataclasses import replace

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.brands import DisabledBrandError, UnknownBrandError, get_brand_registry
from app.database import get_db
from app.policies.belsitec import classify_belsitec_lead
from app.schemas.lead import LeadCreated
from app.schemas.lead_v2 import LeadV2Payload
from app.services.lead_creation import FormNotAllowedError, LeadService, OriginNotAllowedError
from app.services.leads import deliver_lead_notifications

router = APIRouter(prefix="/api/v2/leads", tags=["leads-v2"])


def _device_type(user_agent: str) -> str:
    value = user_agent.casefold()
    if any(token in value for token in ("mobile", "android", "iphone")):
        return "mobile"
    if any(token in value for token in ("ipad", "tablet")):
        return "tablet"
    return "desktop"


@router.post("", response_model=LeadCreated, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
def submit_lead_v2(
    payload: LeadV2Payload,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> LeadCreated:
    command = replace(payload.to_command(), device_type=_device_type(request.headers.get("user-agent", "")))
    if command.brand_key == "belsitec":
        command = replace(
            command,
            classification=classify_belsitec_lead(command.job_title, command.email, command.organization_name),
        )
    try:
        lead = LeadService(get_brand_registry()).create(db, command, request.headers.get("origin"))
    except UnknownBrandError:
        raise HTTPException(status_code=404, detail="Unknown brand.") from None
    except DisabledBrandError:
        raise HTTPException(status_code=403, detail="Brand is disabled.") from None
    except FormNotAllowedError:
        raise HTTPException(status_code=422, detail="Form type is not allowed for this brand.") from None
    except OriginNotAllowedError:
        raise HTTPException(status_code=403, detail="Origin is not allowed for this brand.") from None
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Lead could not be persisted.") from None

    background_tasks.add_task(deliver_lead_notifications, lead.id)
    return LeadCreated(leadId=lead.id)
