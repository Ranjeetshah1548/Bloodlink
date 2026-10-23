"""
OTP-ready phone verification architecture.

`OTP_PROVIDER=console` (default) logs the code to the server console/stdout,
so the full flow (generate -> hash -> store -> verify -> consume -> expire)
is really exercised during development without needing a paid SMS account.

To go live with real SMS, implement `_send_via_twilio` (or another provider)
and set OTP_PROVIDER accordingly in .env - no other code changes needed,
since routes/auth.py only calls `generate_and_send_otp` / `verify_otp`.
"""
import random
import string
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.config import settings
from app import models

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _generate_code() -> str:
    return "".join(random.choices(string.digits, k=settings.OTP_LENGTH))


def _send_via_console(phone: str, code: str) -> None:
    print(f"[OTP:console] Sending code {code} to {phone} (dev mode - not a real SMS)")


def _send_via_twilio(phone: str, code: str) -> None:  # pragma: no cover - requires real credentials
    from twilio.rest import Client  # imported lazily so twilio isn't a hard dependency
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    client.messages.create(
        body=f"Your BloodLink verification code is {code}",
        from_=settings.TWILIO_FROM_NUMBER,
        to=phone,
    )


def generate_and_send_otp(db: Session, user: models.User, purpose: str = "phone_verification") -> None:
    code = _generate_code()
    expires_at = datetime.utcnow() + timedelta(seconds=settings.OTP_EXPIRE_SECONDS)

    otp = models.OTPCode(
        user_id=user.id,
        code_hash=pwd_context.hash(code),
        purpose=purpose,
        expires_at=expires_at,
    )
    db.add(otp)
    db.commit()

    if settings.OTP_PROVIDER == "twilio":
        _send_via_twilio(user.phone, code)
    else:
        _send_via_console(user.phone, code)


def verify_otp(db: Session, user: models.User, code: str, purpose: str = "phone_verification") -> bool:
    candidates = (
        db.query(models.OTPCode)
        .filter(models.OTPCode.user_id == user.id)
        .filter(models.OTPCode.purpose == purpose)
        .filter(models.OTPCode.consumed.is_(False))
        .order_by(models.OTPCode.created_at.desc())
        .all()
    )
    now = datetime.utcnow()
    for otp in candidates:
        if otp.expires_at < now:
            continue
        if pwd_context.verify(code, otp.code_hash):
            otp.consumed = True
            db.commit()
            return True
    return False
