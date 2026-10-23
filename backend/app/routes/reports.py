from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.deps import get_current_user

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("", response_model=schemas.ReportOut, status_code=201)
def file_report(
    payload: schemas.ReportCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if payload.request_id is not None:
        req = db.query(models.BloodRequest).filter(models.BloodRequest.id == payload.request_id).first()
        if not req:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    report = models.Report(reporter_id=user.id, **payload.model_dump())
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("/my", response_model=list[schemas.ReportOut])
def my_reports(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return (db.query(models.Report).filter(models.Report.reporter_id == user.id)
            .order_by(models.Report.created_at.desc()).all())
