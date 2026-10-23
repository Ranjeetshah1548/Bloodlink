from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app import models, schemas
from app.security import hash_password, verify_password, create_access_token


def register_user(db: Session, payload: schemas.UserRegister) -> models.User:
    existing = (
        db.query(models.User)
        .filter((models.User.email == payload.email) | (models.User.phone == payload.phone))
        .first()
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email or phone already registered")

    user = models.User(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email or phone already registered")
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> models.User:
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated")
    return user


def issue_token(user: models.User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role.value})
