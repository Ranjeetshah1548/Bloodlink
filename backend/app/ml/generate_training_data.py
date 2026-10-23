"""
Training-data preparation layer for the donor response-likelihood model.

WHY SYNTHETIC DATA:
A brand-new blood donation platform has no history of donor responses yet,
so there is no real historical_response dataset to train on at day one.
This module generates a clearly-labelled SYNTHETIC dataset that encodes
domain-reasonable assumptions (closer donors respond more, donors with a
strong track record respond more, higher urgency raises response rates,
long gaps since last donation lower willingness, etc.) so the pipeline is
fully trainable and testable end-to-end from day one.

HOW TO SWITCH TO REAL DATA LATER:
Once `donor_responses` has accumulated enough real rows (recommended: a few
thousand), replace the body of `generate_dataset()` with a query against the
`donor_responses` JOIN `donors` JOIN `blood_requests` tables (see the SQL
sketch at the bottom of this file) that reconstructs these same columns from
real history, then re-run train_model.py unchanged - the feature schema
does not need to change.
"""
import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "donor_age",
    "distance_km",
    "is_available",
    "days_since_last_donation",
    "previous_requests",
    "previous_accepts",
    "historical_response_rate",
    "emergency_level",
]
TARGET_COLUMN = "responded_positively"


def generate_dataset(n_rows: int = 6000, random_state: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(random_state)

    donor_age = rng.integers(18, 66, n_rows)
    distance_km = np.round(rng.exponential(scale=12, size=n_rows), 2)
    distance_km = np.clip(distance_km, 0.1, 150)
    is_available = rng.integers(0, 2, n_rows)
    days_since_last_donation = rng.integers(0, 900, n_rows)
    previous_requests = rng.integers(0, 25, n_rows)

    # previous_accepts can't exceed previous_requests
    previous_accepts = np.array([
        rng.integers(0, r + 1) if r > 0 else 0 for r in previous_requests
    ])
    historical_response_rate = np.where(
        previous_requests > 0, previous_accepts / np.maximum(previous_requests, 1), 0.5
    )
    emergency_level = rng.integers(1, 5, n_rows)  # 1=low .. 4=critical

    # ---- Latent probability model (domain assumptions) --------------------
    logit = (
        1.4 * historical_response_rate
        - 0.035 * distance_km
        + 0.55 * is_available
        - 0.0012 * days_since_last_donation
        + 0.18 * emergency_level
        - 0.01 * np.abs(donor_age - 30)
        + 0.05 * np.minimum(previous_requests, 10)
        - 0.9
    )
    prob = 1 / (1 + np.exp(-logit))
    responded_positively = (rng.random(n_rows) < prob).astype(int)

    df = pd.DataFrame({
        "donor_age": donor_age,
        "distance_km": distance_km,
        "is_available": is_available,
        "days_since_last_donation": days_since_last_donation,
        "previous_requests": previous_requests,
        "previous_accepts": previous_accepts,
        "historical_response_rate": np.round(historical_response_rate, 3),
        "emergency_level": emergency_level,
        TARGET_COLUMN: responded_positively,
    })
    return df


# ---------------------------------------------------------------------------
# SQL sketch for switching to REAL historical data once available:
#
# SELECT
#   d.age                                              AS donor_age,
#   dr.distance_km                                     AS distance_km,
#   CAST(d.is_available AS UNSIGNED)                   AS is_available,
#   DATEDIFF(dr.notified_at, d.last_donation_date)     AS days_since_last_donation,
#   d.previous_requests                                AS previous_requests,
#   d.previous_accepts                                 AS previous_accepts,
#   d.historical_response_rate                         AS historical_response_rate,
#   CASE br.urgency WHEN 'low' THEN 1 WHEN 'medium' THEN 2
#                    WHEN 'high' THEN 3 WHEN 'critical' THEN 4 END AS emergency_level,
#   CASE WHEN dr.response = 'accepted' THEN 1 ELSE 0 END AS responded_positively
# FROM donor_responses dr
# JOIN donors d          ON d.id = dr.donor_id
# JOIN blood_requests br ON br.id = dr.request_id
# WHERE dr.response IN ('accepted', 'declined');
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    data = generate_dataset()
    print(data.head())
    print(f"\nGenerated {len(data)} rows. Positive rate: {data[TARGET_COLUMN].mean():.3f}")
