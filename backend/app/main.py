from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import Base, engine
from app import models  # noqa: F401 - ensures models are registered on Base

from app.routes import (
    auth, donors, hospitals, blood_requests, matching,
    donor_responses, notifications, admin, reports,
)

app = FastAPI(
    title="BloodLink API",
    description=(
        "Smart Blood Donation and Donor Matching System.\n\n"
        "Blood-group compatibility is decided by fixed, medically verified rules "
        "(see app/services/compatibility_service.py). The Random Forest ML model "
        "is used ONLY to rank already-eligible donors by predicted response "
        "likelihood - it never decides medical eligibility."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    # Creates any tables that don't yet exist. For production schema changes,
    # use the SQL migration in migrations/schema.sql instead.
    Base.metadata.create_all(bind=engine)


@app.exception_handler(SQLAlchemyError)
def db_exception_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A database error occurred. The operation was rolled back."},
    )


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "BloodLink API", "docs": "/docs"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}


app.include_router(auth.router)
app.include_router(donors.router)
app.include_router(hospitals.router)
app.include_router(blood_requests.router)
app.include_router(matching.router)
app.include_router(donor_responses.router)
app.include_router(notifications.router)
app.include_router(reports.router)
app.include_router(admin.router)
