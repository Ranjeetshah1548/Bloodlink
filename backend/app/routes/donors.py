from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.deps import get_current_user, require_role

router = APIRouter(prefix="/donors", tags=["Donors"])


@router.post("", response_model=schemas.DonorOut, status_code=status.HTTP_201_CREATED)
def create_donor_profile(
    payload: schemas.DonorCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role(models.RoleEnum.donor)),
):
    existing = db.query(models.Donor).filter(models.Donor.user_id == user.id).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Donor profile already exists for this user")

    donor = models.Donor(user_id=user.id, **payload.model_dump())
    db.add(donor)
    db.commit()
    db.refresh(donor)
    return donor


@router.get("/me", response_model=schemas.DonorOut)
def get_my_donor_profile(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role(models.RoleEnum.donor)),
):
    donor = db.query(models.Donor).filter(models.Donor.user_id == user.id).first()
    if not donor:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Donor profile not found. Create one first.")
    return donor


@router.put("/me", response_model=schemas.DonorOut)
def update_my_donor_profile(
    payload: schemas.DonorUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role(models.RoleEnum.donor)),
):
    donor = db.query(models.Donor).filter(models.Donor.user_id == user.id).first()
    if not donor:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Donor profile not found. Create one first.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(donor, field, value)
    db.commit()
    db.refresh(donor)
    return donor


@router.get("/availability", response_model=schemas.DonorOut)
def get_availability(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role(models.RoleEnum.donor)),
):
    donor = db.query(models.Donor).filter(models.Donor.user_id == user.id).first()
    if not donor:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Donor profile not found")
    return donor


@router.put("/availability", response_model=schemas.DonorOut)
def set_availability(
    payload: schemas.AvailabilityUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role(models.RoleEnum.donor)),
):
    donor = db.query(models.Donor).filter(models.Donor.user_id == user.id).first()
    if not donor:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Donor profile not found")
    donor.is_available = payload.is_available
    db.commit()
    db.refresh(donor)
    return donor


@router.get("/me/history", response_model=list[schemas.DonationHistoryOut])
def my_donation_history(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role(models.RoleEnum.donor)),
):
    donor = db.query(models.Donor).filter(models.Donor.user_id == user.id).first()
    if not donor:
        return []
    return (
        db.query(models.DonationHistory)
        .filter(models.DonationHistory.donor_id == donor.id)
        .order_by(models.DonationHistory.donation_date.desc(), models.DonationHistory.id.desc())
        .all()
    )
