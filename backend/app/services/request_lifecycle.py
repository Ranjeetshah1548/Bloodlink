"""
Request lifecycle helpers: expiry + safe status transitions.

Expiry window depends on urgency (a critical request that nobody answered
in 24h should not stay 'live' forever and keep pinging donors).
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app import models

EXPIRY_HOURS = {
    models.UrgencyEnum.critical: 24,
    models.UrgencyEnum.high: 48,
    models.UrgencyEnum.medium: 72,
    models.UrgencyEnum.low: 168,
}

TERMINAL = (
    models.RequestStatusEnum.fulfilled,
    models.RequestStatusEnum.closed,
    models.RequestStatusEnum.expired,
)

# Order used so matching can never move a request *backwards*.
PROGRESS = [
    models.RequestStatusEnum.created,
    models.RequestStatusEnum.hospital_selected,
    models.RequestStatusEnum.compatibility_checked,
    models.RequestStatusEnum.donors_found,
    models.RequestStatusEnum.donors_ranked,
    models.RequestStatusEnum.request_sent,
    models.RequestStatusEnum.donor_accepted,
]


def expires_at(req: models.BloodRequest) -> datetime:
    return req.created_at + timedelta(hours=EXPIRY_HOURS[req.urgency])


def refresh_expiry(db: Session, req: models.BloodRequest) -> bool:
    """Marks the request expired if its window has passed and it is not
    already terminal. Returns True if the request is (now) expired."""
    if req.status == models.RequestStatusEnum.expired:
        return True
    if req.status in TERMINAL:
        return False
    if datetime.utcnow() > expires_at(req):
        req.status = models.RequestStatusEnum.expired
        db.commit()
        return True
    return False


def advance(req: models.BloodRequest, new_status: models.RequestStatusEnum) -> None:
    """Move status forward only; never regress (e.g. re-running matching
    after a donor accepted must not reset the request)."""
    if req.status in TERMINAL:
        return
    if req.status in PROGRESS and PROGRESS.index(new_status) > PROGRESS.index(req.status):
        req.status = new_status
