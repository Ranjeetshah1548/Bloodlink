"""
Core donor-matching workflow:
  1. Eligible blood groups from verified compatibility rules
  2. Filter donors by group + availability + minimum donation interval
  3. Haversine distance donor <-> hospital
  4. Build ML feature vectors
  5. Run Random Forest -> response likelihood
  6. Rank donors by (response_likelihood desc, distance asc)
"""
import math
from datetime import date, datetime
from typing import List

from sqlalchemy.orm import Session

from app import models
from app.services.compatibility_service import eligible_donor_blood_groups
from app.ml.predict import predict_batch, ModelNotTrainedError

MIN_DONATION_INTERVAL_DAYS = 90  # standard whole-blood donation interval
URGENCY_TO_LEVEL = {
    models.UrgencyEnum.low: 1,
    models.UrgencyEnum.medium: 2,
    models.UrgencyEnum.high: 3,
    models.UrgencyEnum.critical: 4,
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)


def days_since(d: date | None, reference: date) -> int:
    if d is None:
        return 9999  # never donated -> treat as long-eligible
    return (reference - d).days


def find_and_rank_donors(db: Session, request: models.BloodRequest) -> List[dict]:
    hospital = request.hospital
    eligible_groups = eligible_donor_blood_groups(request.blood_group.value)

    candidates: List[models.Donor] = (
        db.query(models.Donor)
        .filter(models.Donor.blood_group.in_(eligible_groups))
        .filter(models.Donor.is_available.is_(True))
        .all()
    )

    today = date.today()
    eligible: List[models.Donor] = [
        d for d in candidates
        if days_since(d.last_donation_date, today) >= MIN_DONATION_INTERVAL_DAYS
    ]

    if not eligible:
        return []

    feature_rows = []
    distances = []
    for d in eligible:
        dist = haversine_km(d.latitude, d.longitude, hospital.latitude, hospital.longitude)
        distances.append(dist)
        feature_rows.append({
            "donor_age": d.age,
            "distance_km": dist,
            "is_available": 1 if d.is_available else 0,
            "days_since_last_donation": min(days_since(d.last_donation_date, today), 3650),
            "previous_requests": d.previous_requests,
            "previous_accepts": d.previous_accepts,
            "historical_response_rate": d.historical_response_rate,
            "emergency_level": URGENCY_TO_LEVEL[request.urgency],
        })

    try:
        scores = predict_batch(feature_rows)
    except ModelNotTrainedError:
        # Graceful degradation: fall back to historical_response_rate so the
        # workflow still functions even before the ML model has been trained.
        scores = [d.historical_response_rate for d in eligible]

    ranked = []
    for donor, dist, score in zip(eligible, distances, scores):
        ranked.append({
            "donor": donor,
            "distance_km": dist,
            "response_likelihood": score,
        })

    ranked.sort(key=lambda r: (-r["response_likelihood"], r["distance_km"]))
    return ranked
