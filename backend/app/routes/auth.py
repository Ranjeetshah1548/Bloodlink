from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas, models
from app.services import auth_service, otp_service
from app.deps import get_current_user, bearer_scheme
from app.security import decode_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=schemas.TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.UserRegister, db: Session = Depends(get_db)):
    user = auth_service.register_user(db, payload)
    # Kick off OTP-ready phone verification immediately after registration.
    otp_service.generate_and_send_otp(db, user, purpose="phone_verification")
    token = auth_service.issue_token(user)
    return schemas.TokenResponse(
        access_token=token, role=user.role, user_id=user.id, full_name=user.full_name
    )


@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = auth_service.authenticate_user(db, payload.email, payload.password)
    token = auth_service.issue_token(user)
    return schemas.TokenResponse(
        access_token=token, role=user.role, user_id=user.id, full_name=user.full_name
    )


@router.post("/verify-otp")
def verify_otp(payload: schemas.OTPVerify, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone == payload.phone).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user with that phone number")
    ok = otp_service.verify_otp(db, user, payload.code)
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired OTP")
    user.is_phone_verified = True
    db.commit()
    return {"verified": True}


@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    payload = decode_access_token(credentials.credentials)
    jti = payload.get("jti")
    if jti and not db.query(models.RevokedToken).filter(models.RevokedToken.jti == jti).first():
        db.add(models.RevokedToken(jti=jti))
        db.commit()
    return {"logged_out": True}


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user
