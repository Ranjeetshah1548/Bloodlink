from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.deps import require_role
from app.services.notification_service import notify

router = APIRouter(prefix="/admin", tags=["Admin"])
admin_only = require_role(models.RoleEnum.admin)


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db), _: models.User = Depends(admin_only)):
    return db.query(models.User).order_by(models.User.created_at.desc()).all()


@router.get("/donors", response_model=list[schemas.DonorOut])
def list_donors(db: Session = Depends(get_db), _: models.User = Depends(admin_only)):
    return db.query(models.Donor).order_by(models.Donor.created_at.desc()).all()


@router.get("/hospitals", response_model=list[schemas.HospitalOut])
def list_all_hospitals(db: Session = Depends(get_db), _: models.User = Depends(admin_only)):
    return db.query(models.Hospital).order_by(models.Hospital.created_at.desc()).all()


@router.put("/hospitals/{hospital_id}/verify", response_model=schemas.HospitalOut)
def verify_hospital(
    hospital_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(admin_only),
):
    hospital = db.query(models.Hospital).filter(models.Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hospital not found")
    hospital.is_verified = True
    db.commit()
    db.refresh(hospital)
    return hospital


@router.get("/reports", response_model=list[schemas.ReportOut])
def list_reports(db: Session = Depends(get_db), _: models.User = Depends(admin_only)):
    return db.query(models.Report).order_by(models.Report.created_at.desc()).all()


@router.put("/reports/{report_id}", response_model=schemas.ReportOut)
def update_report(
    report_id: int,
    payload: schemas.ReportStatusUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(admin_only),
):
    report = db.query(models.Report).filter(models.Report.id == report_id).first()
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    report.status = payload.status
    db.commit()
    db.refresh(report)
    return report


@router.put("/users/{user_id}/active", response_model=schemas.UserOut)
def set_user_active(
    user_id: int,
    payload: schemas.ActiveUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(admin_only),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account")
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user
