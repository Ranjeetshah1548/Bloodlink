from sqlalchemy.orm import Session
from app import models


def notify(db: Session, user_id: int, title: str, message: str, type_: str = "general",
           related_request_id: int | None = None, commit: bool = True) -> models.Notification:
    note = models.Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=type_,
        related_request_id=related_request_id,
    )
    db.add(note)
    if commit:
        db.commit()
        db.refresh(note)
    return note
