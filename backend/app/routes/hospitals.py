from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.deps import require_role
from app.services.matching_service import haversine_km

router = APIRouter(prefix="/hospitals", tags=["Hospitals"])


@router.get("", response_model=list[schemas.HospitalOut])
def list_hospitals(
    city: Optional[str] = None,
    verified_only: bool = True,
    lat: Optional[float] = Query(default=None),
    lng: Optional[float] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(models.Hospital)
    if verified_only:
        q = q.filter(models.Hospital.is_verified.is_(True))
    if city:
        q = q.filter(models.Hospital.city.ilike(f"%{city}%"))
    hospitals = q.order_by(models.Hospital.name).all()

    results = []
    for h in hospitals:
        item = schemas.HospitalOut.model_validate(h)
        if lat is not None and lng is not None:
            item.distance_km = haversine_km(lat, lng, h.latitude, h.longitude)
        results.append(item)

    if lat is not None and lng is not None:
        results.sort(key=lambda r: r.distance_km if r.distance_km is not None else 1e9)
    return results


@router.get("/{hospital_id}", response_model=schemas.HospitalOut)
def get_hospital(hospital_id: int, db: Session = Depends(get_db)):
    hospital = db.query(models.Hospital).filter(models.Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hospital not found")
    return hospital


@router.post("", response_model=schemas.HospitalOut, status_code=status.HTTP_201_CREATED)
def create_hospital(
    payload: schemas.HospitalCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role(models.RoleEnum.admin)),
):
    hospital = models.Hospital(**payload.model_dump(), is_verified=False)
    db.add(hospital)
    db.commit()
    db.refresh(hospital)
    return hospital
