"""
Blood-group compatibility rules.

These are standard, medically verified donor -> recipient compatibility
rules (ABO + Rh). They are a fixed lookup table, NOT inferred or predicted
by machine learning, per project requirements. The ML model in app/ml is
only ever applied AFTER this filter, to rank already-eligible donors.
"""
from typing import List
from app.models import BloodGroupEnum

# For a recipient of a given blood group, which donor blood groups are
# medically compatible (donor -> recipient direction).
COMPATIBLE_DONORS: dict[str, List[str]] = {
    "A+":  ["A+", "A-", "O+", "O-"],
    "A-":  ["A-", "O-"],
    "B+":  ["B+", "B-", "O+", "O-"],
    "B-":  ["B-", "O-"],
    "AB+": ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],  # universal recipient
    "AB-": ["A-", "B-", "AB-", "O-"],
    "O+":  ["O+", "O-"],
    "O-":  ["O-"],  # universal donor, but can only receive O-
}


def eligible_donor_blood_groups(recipient_blood_group: BloodGroupEnum | str) -> List[str]:
    """Returns the list of donor blood groups that may safely donate to a
    recipient/request of the given blood group."""
    key = recipient_blood_group.value if isinstance(recipient_blood_group, BloodGroupEnum) else recipient_blood_group
    if key not in COMPATIBLE_DONORS:
        raise ValueError(f"Unknown blood group: {key}")
    return COMPATIBLE_DONORS[key]


def is_compatible(donor_blood_group: str, recipient_blood_group: str) -> bool:
    return donor_blood_group in eligible_donor_blood_groups(recipient_blood_group)
