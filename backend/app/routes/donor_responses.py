from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.deps import require_role
from app.services.notification_service import notify
from app.services.request_lifecycle import refresh_expiry, advance, TERMINAL

router = APIRouter(prefix="/donor-responses", tags=["Donor Responses"])


@router.post("", response_model=schemas.DonorResponseOut)
def answer_donor_request(
    payload: schemas.DonorResponseCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role(models.RoleEnum.donor)),
):
    donor = db.query(models.Donor).filter(models.Donor.user_id == user.id).first()
    if not donor or donor.id != payload.donor_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You may only respond as yourself")

    dr = (
        db.query(models.DonorResponse)
        .filter(models.DonorResponse.request_id == payload.request_id,
                models.DonorResponse.donor_id == payload.donor_id)
        .first()
    )
    if not dr:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You were not notified for this request")
    if dr.response != models.ResponseEnum.pending:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You already responded to this request")

    req = db.query(models.BloodRequest).filter(models.BloodRequest.id == dr.request_id).first()
    if refresh_expiry(db, req):
        raise HTTPException(status.HTTP_410_GONE, "This request has expired")
    if req.status in TERMINAL:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This request is no longer active")
    if payload.response == models.ResponseEnum.pending:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Response must be 'accepted' or 'declined'")
    if payload.response == models.ResponseEnum.accepted and not donor.is_available:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You are marked unavailable. Turn availability on first.")

    dr.response = payload.response
    dr.responded_at = datetime.utcnow()

    if payload.response == models.ResponseEnum.accepted:
        donor.previous_accepts += 1
        advance(req, models.RequestStatusEnum.donor_accepted)
        notify(db, req.requester_id, "A donor accepted your request",
               f"{user.full_name} has accepted your blood request #{req.id}. Their phone number is now visible on the request page.",
               "donor_accept", req.id, commit=False)
    else:
        notify(db, req.requester_id, "A donor declined",
               f"A matched donor declined request #{req.id}. Other ranked donors are still pending.",
               "donor_decline", req.id, commit=False)

    if donor.previous_requests > 0:
        donor.historical_response_rate = round(donor.previous_accepts / donor.previous_requests, 3)

    db.commit()
    db.refresh(dr)
    return dr


@router.get("/my", response_model=list[schemas.DonorResponseOut])
def my_donor_responses(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role(models.RoleEnum.donor)),
):
    donor = db.query(models.Donor).filter(models.Donor.user_id == user.id).first()
    if not donor:
        return []
    return (
        db.query(models.DonorResponse)
        .filter(models.DonorResponse.donor_id == donor.id)
        .order_by(models.DonorResponse.notified_at.desc())
        .all()
    )
