from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator

from app.models import RoleEnum, BloodGroupEnum, UrgencyEnum, RequestStatusEnum, ResponseEnum, ReportStatusEnum


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class UserRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    role: RoleEnum = RoleEnum.recipient

    @field_validator("role")
    @classmethod
    def no_self_service_admin(cls, v):
        # Admin accounts can never be self-registered; use `python create_admin.py`.
        if v == RoleEnum.admin:
            raise ValueError("Admin accounts cannot be self-registered")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: RoleEnum
    user_id: int
    full_name: str


class OTPRequest(BaseModel):
    phone: str


class OTPVerify(BaseModel):
    phone: str
    code: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: EmailStr
    phone: str
    role: RoleEnum
    is_phone_verified: bool
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Donor
# ---------------------------------------------------------------------------
class DonorCreate(BaseModel):
    blood_group: BloodGroupEnum
    age: int = Field(ge=18, le=65)
    city: str
    latitude: float
    longitude: float
    last_donation_date: Optional[date] = None
    is_available: bool = True


class DonorUpdate(BaseModel):
    blood_group: Optional[BloodGroupEnum] = None
    age: Optional[int] = Field(default=None, ge=18, le=65)
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    last_donation_date: Optional[date] = None
    is_available: Optional[bool] = None


class DonorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    blood_group: BloodGroupEnum
    age: int
    city: str
    latitude: float
    longitude: float
    last_donation_date: Optional[date]
    is_available: bool
    total_donations: int
    previous_requests: int
    previous_accepts: int
    historical_response_rate: float
    created_at: datetime


class AvailabilityUpdate(BaseModel):
    is_available: bool


# ---------------------------------------------------------------------------
# Hospital
# ---------------------------------------------------------------------------
class HospitalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    address: str
    city: str
    latitude: float
    longitude: float
    is_verified: bool
    contact: str
    created_at: datetime
    distance_km: Optional[float] = None


class HospitalCreate(BaseModel):
    name: str
    address: str
    city: str
    latitude: float
    longitude: float
    contact: str


# ---------------------------------------------------------------------------
# Blood Requests
# ---------------------------------------------------------------------------
class BloodRequestCreate(BaseModel):
    hospital_id: int
    blood_group: BloodGroupEnum
    units_required: int = Field(ge=1, le=20)
    urgency: UrgencyEnum = UrgencyEnum.medium
    notes: Optional[str] = None
    patient_name: str = Field(min_length=2, max_length=120)
    contact_name: str = Field(min_length=2, max_length=120)
    contact_phone: str = Field(min_length=7, max_length=20, pattern=r"^\+?[0-9][0-9\s\-]{6,18}$")
    ward_info: Optional[str] = Field(default=None, max_length=150)


class BloodRequestUpdate(BaseModel):
    status: Optional[RequestStatusEnum] = None
    units_required: Optional[int] = Field(default=None, ge=1, le=20)
    urgency: Optional[UrgencyEnum] = None
    notes: Optional[str] = None


class BloodRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    requester_id: int
    hospital_id: int
    blood_group: BloodGroupEnum
    units_required: int
    urgency: UrgencyEnum
    status: RequestStatusEnum
    notes: Optional[str]
    patient_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    ward_info: Optional[str] = None
    created_at: datetime
    fulfilled_at: Optional[datetime]


class DonorRequestOut(BaseModel):
    """What a DONOR is allowed to see about a request. Contact fields are
    None until this donor has accepted (contact_visible == True)."""
    id: int
    blood_group: BloodGroupEnum
    units_required: int
    urgency: UrgencyEnum
    status: RequestStatusEnum
    created_at: datetime
    hospital_id: int
    hospital_name: str
    hospital_address: str
    my_response: ResponseEnum
    contact_visible: bool
    notes: Optional[str] = None
    patient_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    ward_info: Optional[str] = None
    hospital_contact: Optional[str] = None


class ResponderOut(BaseModel):
    """A donor who was contacted for a request, as seen by the requester.
    phone is only filled once that donor has accepted."""
    donor_id: int
    donor_name: str
    blood_group: BloodGroupEnum
    response: ResponseEnum
    distance_km: Optional[float]
    responded_at: Optional[datetime]
    phone: Optional[str] = None


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------
class RankedDonorOut(BaseModel):
    donor_id: int
    donor_name: str
    blood_group: BloodGroupEnum
    city: str
    distance_km: float
    days_since_last_donation: Optional[int]
    historical_response_rate: float
    response_likelihood: float = Field(description="ML model output, 0-1. Prioritization signal only.")
    request_status: Optional[str] = Field(default=None, description="pending/accepted/declined if already contacted for this request")


class MatchResultOut(BaseModel):
    request_id: int
    eligible_blood_groups: List[str]
    total_eligible_donors: int
    ranked_donors: List[RankedDonorOut]


# ---------------------------------------------------------------------------
# Donor Response
# ---------------------------------------------------------------------------
class DonorResponseCreate(BaseModel):
    request_id: int
    donor_id: int
    response: ResponseEnum


class DonorResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    request_id: int
    donor_id: int
    match_score: Optional[float]
    distance_km: Optional[float]
    response: ResponseEnum
    notified_at: datetime
    responded_at: Optional[datetime]


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    message: str
    type: str
    related_request_id: Optional[int]
    is_read: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
class ReportCreate(BaseModel):
    request_id: Optional[int] = None
    reason: str
    description: Optional[str] = None


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reporter_id: int
    request_id: Optional[int]
    reason: str
    description: Optional[str]
    status: ReportStatusEnum
    created_at: datetime


class ReportStatusUpdate(BaseModel):
    status: ReportStatusEnum


# ---------------------------------------------------------------------------
# Send donor requests / donation history / admin
# ---------------------------------------------------------------------------
class SendRequestsIn(BaseModel):
    donor_ids: List[int] = Field(min_length=1, max_length=25)


class SendRequestsOut(BaseModel):
    request_id: int
    sent_to: List[int]
    skipped: List[int]
    status: RequestStatusEnum


class DonationHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    donor_id: int
    request_id: Optional[int]
    hospital_id: Optional[int]
    donation_date: date
    units_donated: int
    created_at: datetime


class ActiveUpdate(BaseModel):
    is_active: bool
