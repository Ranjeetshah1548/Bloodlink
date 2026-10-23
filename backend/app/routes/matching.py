from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.deps import get_current_user
from app.services.compatibility_service import eligible_donor_blood_groups
from app.services.matching_service import find_and_rank_donors
from app.services.notification_service import notify
from app.services.request_lifecycle import refresh_expiry, advance, TERMINAL

router = APIRouter(tags=["Matching"])


def _load_request(db: Session, request_id: int, user: models.User) -> models.BloodRequest:
    req = db.query(models.BloodRequest).filter(models.BloodRequest.id == request_id).first()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Blood request not found")
    if user.role == models.RoleEnum.donor:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Donors cannot run matching")
    if user.role == models.RoleEnum.recipient and req.requester_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your request")
    if refresh_expiry(db, req):
        raise HTTPException(status.HTTP_410_GONE, "This request has expired")
    if req.status in TERMINAL:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This request is no longer active")
    return req


@router.post("/match-donors/{request_id}", response_model=schemas.MatchResultOut)
def match_donors(
    request_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Compatibility check -> eligibility filters -> distance -> Random Forest
    ranking. Returns the ranked list; does NOT notify anyone. The recipient
    chooses who to contact via POST /match-donors/{id}/send."""
    req = _load_request(db, request_id, user)

    advance(req, models.RequestStatusEnum.compatibility_checked)
    eligible_groups = eligible_donor_blood_groups(req.blood_group.value)
    ranked = find_and_rank_donors(db, req)
    if ranked:
        advance(req, models.RequestStatusEnum.donors_found)
        advance(req, models.RequestStatusEnum.donors_ranked)
    db.commit()

    already = {
        r.donor_id: r.response for r in
        db.query(models.DonorResponse).filter(models.DonorResponse.request_id == req.id).all()
    }

    out = []
    for entry in ranked:
        donor: models.Donor = entry["donor"]
        out.append(schemas.RankedDonorOut(
            donor_id=donor.id,
            donor_name=donor.user.full_name,
            blood_group=donor.blood_group,
            city=donor.city,
            distance_km=entry["distance_km"],
            days_since_last_donation=(
                None if donor.last_donation_date is None
                else (req.created_at.date() - donor.last_donation_date).days
            ),
            historical_response_rate=donor.historical_response_rate,
            response_likelihood=entry["response_likelihood"],
            request_status=already[donor.id].value if donor.id in already else None,
        ))

    return schemas.MatchResultOut(
        request_id=req.id,
        eligible_blood_groups=eligible_groups,
        total_eligible_donors=len(out),
        ranked_donors=out,
    )


@router.post("/match-donors/{request_id}/send", response_model=schemas.SendRequestsOut)
def send_donor_requests(
    request_id: int,
    payload: schemas.SendRequestsIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Recipient sends the request to chosen donors. Every chosen donor is
    re-validated server-side against the same eligibility pipeline, so the
    client can never notify an incompatible/unavailable donor."""
    req = _load_request(db, request_id, user)

    eligible = {e["donor"].id: e for e in find_and_rank_donors(db, req)}
    sent, skipped = [], []

    for donor_id in dict.fromkeys(payload.donor_ids):
        entry = eligible.get(donor_id)
        if entry is None:
            skipped.append(donor_id)          # not compatible / unavailable / too recent
            continue
        exists = db.query(models.DonorResponse).filter(
            models.DonorResponse.request_id == req.id,
            models.DonorResponse.donor_id == donor_id).first()
        if exists:
            skipped.append(donor_id)
            continue
        donor = entry["donor"]
        db.add(models.DonorResponse(
            request_id=req.id, donor_id=donor_id,
            match_score=entry["response_likelihood"], distance_km=entry["distance_km"],
        ))
        donor.previous_requests += 1
        notify(
            db, donor.user_id, "New blood request near you",
            f"A {req.urgency.value} priority request for {req.blood_group.value} blood "
            f"needs {req.units_required} unit(s) at {req.hospital.name} "
            f"({entry['distance_km']} km away). Please respond.",
            "match_request", req.id, commit=False,
        )
        sent.append(donor_id)

    if not sent and not skipped:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No donors selected")
    if not sent:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "None of the selected donors can be contacted (ineligible or already contacted)")

    advance(req, models.RequestStatusEnum.request_sent)
    db.commit()
    return schemas.SendRequestsOut(request_id=req.id, sent_to=sent, skipped=skipped, status=req.status)
