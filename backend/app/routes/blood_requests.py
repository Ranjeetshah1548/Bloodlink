from datetime import datetime
from typing import Union

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.deps import get_current_user, require_role
from app.services.notification_service import notify
from app.services.request_lifecycle import refresh_expiry

router = APIRouter(prefix="/blood-requests", tags=["Blood Requests"])


@router.post("", response_model=schemas.BloodRequestOut, status_code=status.HTTP_201_CREATED)
def create_blood_request(
    payload: schemas.BloodRequestCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    hospital = db.query(models.Hospital).filter(models.Hospital.id == payload.hospital_id).first()
    if not hospital:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Selected hospital does not exist")
    if not hospital.is_verified:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Selected hospital is not a verified hospital")

    req = models.BloodRequest(
        requester_id=user.id,
        hospital_id=hospital.id,
        blood_group=payload.blood_group,
        units_required=payload.units_required,
        urgency=payload.urgency,
        notes=payload.notes,
        patient_name=payload.patient_name.strip(),
        contact_name=payload.contact_name.strip(),
        contact_phone=payload.contact_phone.strip(),
        ward_info=(payload.ward_info or "").strip() or None,
        status=models.RequestStatusEnum.hospital_selected,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def _donor_view(req: models.BloodRequest, resp: models.DonorResponse) -> schemas.DonorRequestOut:
    """Contact details are released to a donor only after THEY accepted."""
    visible = resp.response == models.ResponseEnum.accepted
    return schemas.DonorRequestOut(
        id=req.id, blood_group=req.blood_group, units_required=req.units_required,
        urgency=req.urgency, status=req.status, created_at=req.created_at,
        hospital_id=req.hospital_id, hospital_name=req.hospital.name,
        hospital_address=f"{req.hospital.address}, {req.hospital.city}",
        my_response=resp.response, contact_visible=visible,
        notes=req.notes if visible else None,
        patient_name=req.patient_name if visible else None,
        contact_name=req.contact_name if visible else None,
        contact_phone=req.contact_phone if visible else None,
        ward_info=req.ward_info if visible else None,
        hospital_contact=req.hospital.contact if visible else None,
    )


def _my_donor(db: Session, user: models.User):
    return db.query(models.Donor).filter(models.Donor.user_id == user.id).first()


@router.get("", response_model=list[Union[schemas.BloodRequestOut, schemas.DonorRequestOut]])
def list_blood_requests(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Recipients: their own requests. Admin: all. Donors: only requests they
    were contacted for, WITHOUT contact details until they accept."""
    if user.role == models.RoleEnum.donor:
        donor = _my_donor(db, user)
        if not donor:
            return []
        pairs = (
            db.query(models.DonorResponse)
            .filter(models.DonorResponse.donor_id == donor.id)
            .order_by(models.DonorResponse.notified_at.desc()).all()
        )
        for r in pairs:
            refresh_expiry(db, r.request)
        return [_donor_view(r.request, r) for r in pairs]

    q = db.query(models.BloodRequest)
    if user.role == models.RoleEnum.recipient:
        q = q.filter(models.BloodRequest.requester_id == user.id)
    rows = q.order_by(models.BloodRequest.created_at.desc()).all()
    for r in rows:
        refresh_expiry(db, r)
    return rows


@router.get("/{request_id}", response_model=Union[schemas.BloodRequestOut, schemas.DonorRequestOut])
def get_blood_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    req = db.query(models.BloodRequest).filter(models.BloodRequest.id == request_id).first()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Blood request not found")
    if user.role == models.RoleEnum.recipient and req.requester_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your request")
    refresh_expiry(db, req)
    if user.role == models.RoleEnum.donor:
        donor = _my_donor(db, user)
        resp = donor and db.query(models.DonorResponse).filter(
            models.DonorResponse.request_id == req.id, models.DonorResponse.donor_id == donor.id).first()
        if not resp:
            # a donor may only see requests they were actually contacted for
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You were not contacted for this request")
        return _donor_view(req, resp)
    return req


@router.get("/{request_id}/responders", response_model=list[schemas.ResponderOut])
def request_responders(
    request_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Donors contacted for this request and their answers. A donor's phone is
    revealed to the requester only after that donor accepted."""
    req = db.query(models.BloodRequest).filter(models.BloodRequest.id == request_id).first()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Blood request not found")
    if user.role == models.RoleEnum.donor or (
            user.role == models.RoleEnum.recipient and req.requester_id != user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your request")
    rows = (db.query(models.DonorResponse).filter(models.DonorResponse.request_id == req.id)
            .order_by(models.DonorResponse.match_score.desc()).all())
    return [
        schemas.ResponderOut(
            donor_id=r.donor_id, donor_name=r.donor.user.full_name, blood_group=r.donor.blood_group,
            response=r.response, distance_km=r.distance_km, responded_at=r.responded_at,
            phone=r.donor.user.phone if r.response == models.ResponseEnum.accepted else None,
        ) for r in rows
    ]


@router.put("/{request_id}", response_model=schemas.BloodRequestOut)
def update_blood_request(
    request_id: int,
    payload: schemas.BloodRequestUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    req = db.query(models.BloodRequest).filter(models.BloodRequest.id == request_id).first()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Blood request not found")
    if user.role not in (models.RoleEnum.admin,) and req.requester_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your request")
    if refresh_expiry(db, req):
        raise HTTPException(status.HTTP_410_GONE, "This request has expired and cannot be modified")
    if req.status in (models.RequestStatusEnum.closed, models.RequestStatusEnum.fulfilled):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This request is already finished and cannot be modified")

    data = payload.model_dump(exclude_unset=True)
    new_status = data.get("status")
    if new_status is not None:
        # Only terminal transitions are user-driven; every other status is
        # advanced by the matching / donor-response pipeline.
        if new_status not in (models.RequestStatusEnum.fulfilled, models.RequestStatusEnum.closed):
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "Status can only be set to 'fulfilled' or 'closed'")
        if new_status == models.RequestStatusEnum.fulfilled and \
                req.status != models.RequestStatusEnum.donor_accepted:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "A request can only be fulfilled after a donor has accepted")
    if "status" in data and data["status"] == models.RequestStatusEnum.fulfilled:
        req.fulfilled_at = datetime.utcnow()
        # record donation history for any donor who accepted
        accepted = (
            db.query(models.DonorResponse)
            .filter(models.DonorResponse.request_id == req.id)
            .filter(models.DonorResponse.response == models.ResponseEnum.accepted)
            .all()
        )
        for resp in accepted:
            donor = resp.donor
            donor.total_donations += 1
            donor.last_donation_date = datetime.utcnow().date()
            db.add(models.DonationHistory(
                donor_id=donor.id, request_id=req.id, hospital_id=req.hospital_id,
                donation_date=datetime.utcnow().date(), units_donated=1,
            ))
        notify(db, req.requester_id, "Request fulfilled",
               f"Your blood request #{req.id} has been marked fulfilled.", "request_update",
               req.id, commit=False)

    for field, value in data.items():
        setattr(req, field, value)
    db.commit()
    db.refresh(req)
    return req
