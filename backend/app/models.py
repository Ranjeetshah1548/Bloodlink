import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, Double, Date, DateTime,
    ForeignKey, Text, Enum, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


class RoleEnum(str, enum.Enum):
    donor = "donor"
    recipient = "recipient"
    admin = "admin"


class BloodGroupEnum(str, enum.Enum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"


class UrgencyEnum(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RequestStatusEnum(str, enum.Enum):
    created = "created"
    hospital_selected = "hospital_selected"
    compatibility_checked = "compatibility_checked"
    donors_found = "donors_found"
    donors_ranked = "donors_ranked"
    request_sent = "request_sent"
    donor_accepted = "donor_accepted"
    fulfilled = "fulfilled"
    closed = "closed"
    expired = "expired"


class ResponseEnum(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"


class ReportStatusEnum(str, enum.Enum):
    open = "open"
    reviewing = "reviewing"
    resolved = "resolved"
    dismissed = "dismissed"


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
def _enum(enum_cls):
    """Persist the enum *values* ('A+', 'critical', ...) so the MySQL ENUM
    definitions match migrations/schema.sql and are readable in raw SQL."""
    return Enum(enum_cls, values_callable=lambda e: [m.value for m in e])


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(_enum(RoleEnum), nullable=False, default=RoleEnum.recipient)
    is_phone_verified = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    donor_profile = relationship("Donor", back_populates="user", uselist=False, cascade="all, delete-orphan")
    blood_requests = relationship("BloodRequest", back_populates="requester", foreign_keys="BloodRequest.requester_id")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    reports_filed = relationship("Report", back_populates="reporter", foreign_keys="Report.reporter_id")
    otp_codes = relationship("OTPCode", back_populates="user", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# OTP (phone verification architecture)
# ---------------------------------------------------------------------------
class OTPCode(Base):
    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash = Column(String(255), nullable=False)
    purpose = Column(String(30), nullable=False, default="phone_verification")
    expires_at = Column(DateTime, nullable=False)
    consumed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="otp_codes")


# ---------------------------------------------------------------------------
# donors
# ---------------------------------------------------------------------------
class Donor(Base):
    __tablename__ = "donors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    blood_group = Column(_enum(BloodGroupEnum), nullable=False, index=True)
    age = Column(Integer, nullable=False)
    city = Column(String(100), nullable=False, index=True)
    latitude = Column(Double, nullable=False)
    longitude = Column(Double, nullable=False)
    last_donation_date = Column(Date, nullable=True)
    is_available = Column(Boolean, default=True, nullable=False, index=True)
    total_donations = Column(Integer, default=0, nullable=False)
    previous_requests = Column(Integer, default=0, nullable=False)
    previous_accepts = Column(Integer, default=0, nullable=False)
    historical_response_rate = Column(Double, default=0.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="donor_profile")
    responses = relationship("DonorResponse", back_populates="donor", cascade="all, delete-orphan")
    donations = relationship("DonationHistory", back_populates="donor", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_donor_group_avail_city", "blood_group", "is_available", "city"),
    )


# ---------------------------------------------------------------------------
# hospitals
# ---------------------------------------------------------------------------
class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    address = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    latitude = Column(Double, nullable=False)
    longitude = Column(Double, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False, index=True)
    contact = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    blood_requests = relationship("BloodRequest", back_populates="hospital")


# ---------------------------------------------------------------------------
# blood_requests
# ---------------------------------------------------------------------------
class BloodRequest(Base):
    __tablename__ = "blood_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    requester_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)
    blood_group = Column(_enum(BloodGroupEnum), nullable=False, index=True)
    units_required = Column(Integer, nullable=False, default=1)
    urgency = Column(_enum(UrgencyEnum), nullable=False, default=UrgencyEnum.medium)
    status = Column(_enum(RequestStatusEnum), nullable=False, default=RequestStatusEnum.created, index=True)
    notes = Column(Text, nullable=True)
    # Contact details for the people involved. Shown to a donor ONLY after
    # that donor accepts (see routes/blood_requests.py -> _donor_view).
    patient_name = Column(String(120), nullable=True)
    contact_name = Column(String(120), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    ward_info = Column(String(150), nullable=True)     # ward / bed / floor
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    fulfilled_at = Column(DateTime, nullable=True)

    requester = relationship("User", back_populates="blood_requests", foreign_keys=[requester_id])
    hospital = relationship("Hospital", back_populates="blood_requests")
    responses = relationship("DonorResponse", back_populates="request", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="request")

    __table_args__ = (
        Index("ix_request_status_group", "status", "blood_group"),
    )


# ---------------------------------------------------------------------------
# donor_responses  (ranked/notified donors + their accept/decline)
# ---------------------------------------------------------------------------
class DonorResponse(Base):
    __tablename__ = "donor_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey("blood_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    donor_id = Column(Integer, ForeignKey("donors.id", ondelete="CASCADE"), nullable=False, index=True)
    match_score = Column(Double, nullable=True)         # ML response-likelihood at time of ranking
    distance_km = Column(Double, nullable=True)
    response = Column(_enum(ResponseEnum), nullable=False, default=ResponseEnum.pending, index=True)
    notified_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    responded_at = Column(DateTime, nullable=True)

    request = relationship("BloodRequest", back_populates="responses")
    donor = relationship("Donor", back_populates="responses")

    __table_args__ = (
        UniqueConstraint("request_id", "donor_id", name="uq_request_donor"),
    )


# ---------------------------------------------------------------------------
# notifications
# ---------------------------------------------------------------------------
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(40), nullable=False, default="general")
    related_request_id = Column(Integer, ForeignKey("blood_requests.id"), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="notifications")


# ---------------------------------------------------------------------------
# reports
# ---------------------------------------------------------------------------
class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reporter_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    request_id = Column(Integer, ForeignKey("blood_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    reason = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(_enum(ReportStatusEnum), nullable=False, default=ReportStatusEnum.open, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    reporter = relationship("User", back_populates="reports_filed", foreign_keys=[reporter_id])
    request = relationship("BloodRequest", back_populates="reports")


# ---------------------------------------------------------------------------
# donation_history
# ---------------------------------------------------------------------------
class RevokedToken(Base):
    """Stores the jti of tokens that have been logged out, so /auth/logout
    has a real, enforced effect even though JWTs are otherwise stateless."""
    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    jti = Column(String(64), unique=True, nullable=False, index=True)
    revoked_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DonationHistory(Base):
    __tablename__ = "donation_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    donor_id = Column(Integer, ForeignKey("donors.id", ondelete="CASCADE"), nullable=False, index=True)
    request_id = Column(Integer, ForeignKey("blood_requests.id"), nullable=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=True)
    donation_date = Column(Date, nullable=False)
    units_donated = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    donor = relationship("Donor", back_populates="donations")
