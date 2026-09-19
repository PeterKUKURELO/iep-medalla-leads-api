from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Complaint
from app.schemas.complaint import ComplaintCreate, ComplaintCreated

router = APIRouter(prefix="/api/v1/complaints", tags=["complaints"])


@router.post("", response_model=ComplaintCreated, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
def submit_complaint(payload: ComplaintCreate, db: Session = Depends(get_db)) -> ComplaintCreated:
    complaint = Complaint(**payload.persistence_data())
    try:
        db.add(complaint)
        db.commit()
        db.refresh(complaint)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible registrar el reclamo.") from None
    return ComplaintCreated(complaintId=complaint.id)
