from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.leads import create_lead
from app.schemas.lead import LeadCreate, LeadCreated
from app.services.leads import deliver_lead_notifications

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/leads", tags=["leads"])


@router.post("", response_model=LeadCreated, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
def submit_lead(
    payload: LeadCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> LeadCreated:
    limiter = request.app.state.rate_limiter
    client_ip = request.client.host if request.client else "unknown"
    if not limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Demasiados intentos. Intenta nuevamente en unos minutos.")

    try:
        lead = create_lead(db, payload)
    except SQLAlchemyError:
        logger.exception("lead_persistence_failed", extra={"form_type": payload.form_type})
        raise HTTPException(status_code=500, detail="No fue posible guardar tus datos.") from None

    background_tasks.add_task(deliver_lead_notifications, lead.id)
    return LeadCreated(leadId=lead.id)
