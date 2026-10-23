"""
DEVELOPMENT SEED DATA - not for production use.

Populates the database with a realistic set of sample users, donors,
verified hospitals, blood requests, and donor-response history so the
whole application can be explored immediately after setup.

Run with:  python seed.py   (from backend/, with your venv + .env active)
"""
import random
from datetime import date, timedelta, datetime

from app.database import SessionLocal, Base, engine
from app import models
from app.security import hash_password

random.seed(7)

CITIES = [
    ("Amritsar", 31.6340, 74.8723),
    ("Chandigarh", 30.7333, 76.7794),
    ("Ludhiana", 30.9010, 75.8573),
    ("Delhi", 28.7041, 77.1025),
    ("Jalandhar", 31.3260, 75.5762),
]

BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

HOSPITAL_NAMES = [
    "City Care General Hospital", "Sunrise Multispecialty Hospital",
    "Guru Nanak Dev Hospital", "Fortis Wellness Hospital",
    "Civil Hospital", "Apex Trauma & Medical Center",
    "Lifeline Community Hospital", "Sacred Heart Hospital",
]


def jitter(lat, lng):
    return round(lat + random.uniform(-0.05, 0.05), 6), round(lng + random.uniform(-0.05, 0.05), 6)


def run():
    print("Creating tables if they don't exist...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        if db.query(models.User).count() > 0:
            print("Database already has data. Aborting seed to avoid duplicates.")
            print("Drop the database (or truncate tables) first if you want to reseed.")
            return

        # ---- Admin -----------------------------------------------------
        admin = models.User(
            full_name="System Admin", email="admin@bloodlink.dev", phone="+910000000001",
            password_hash=hash_password("Admin@1234"), role=models.RoleEnum.admin,
            is_phone_verified=True,
        )
        db.add(admin)

        # ---- Hospitals ---------------------------------------------------
        hospitals = []
        for i, name in enumerate(HOSPITAL_NAMES):
            city, lat, lng = CITIES[i % len(CITIES)]
            hlat, hlng = jitter(lat, lng)
            h = models.Hospital(
                name=name, address=f"{100+i} Health Street, {city}", city=city,
                latitude=hlat, longitude=hlng,
                is_verified=(i != len(HOSPITAL_NAMES) - 1),  # leave one unverified for admin demo
                contact=f"+91-11-4000-{1000+i}",
            )
            hospitals.append(h)
            db.add(h)
        db.flush()

        # ---- Donors --------------------------------------------------------
        donors = []
        for i in range(40):
            city, lat, lng = CITIES[i % len(CITIES)]
            dlat, dlng = jitter(lat, lng)
            user = models.User(
                full_name=f"Donor {i+1}",
                email=f"donor{i+1}@bloodlink.dev",
                phone=f"+9199900{1000+i}",
                password_hash=hash_password("Donor@1234"),
                role=models.RoleEnum.donor,
                is_phone_verified=True,
            )
            db.add(user)
            db.flush()

            prev_requests = random.randint(0, 15)
            prev_accepts = random.randint(0, prev_requests) if prev_requests else 0
            last_donation = (
                date.today() - timedelta(days=random.randint(10, 500))
                if random.random() > 0.2 else None
            )
            donor = models.Donor(
                user_id=user.id,
                blood_group=random.choice(BLOOD_GROUPS),
                age=random.randint(19, 58),
                city=city,
                latitude=dlat, longitude=dlng,
                last_donation_date=last_donation,
                is_available=random.random() > 0.15,
                total_donations=prev_accepts,
                previous_requests=prev_requests,
                previous_accepts=prev_accepts,
                historical_response_rate=round(prev_accepts / prev_requests, 3) if prev_requests else 0.5,
            )
            db.add(donor)
            donors.append(donor)
        db.flush()

        # ---- Recipients ------------------------------------------------
        recipients = []
        for i in range(6):
            user = models.User(
                full_name=f"Recipient {i+1}",
                email=f"recipient{i+1}@bloodlink.dev",
                phone=f"+9188800{1000+i}",
                password_hash=hash_password("Recipient@1234"),
                role=models.RoleEnum.recipient,
                is_phone_verified=True,
            )
            db.add(user)
            recipients.append(user)
        db.flush()

        # ---- Sample blood requests + donor response history ---------------
        verified_hospitals = [h for h in hospitals if h.is_verified]
        statuses_history = [models.RequestStatusEnum.fulfilled, models.RequestStatusEnum.closed]
        for i in range(10):
            requester = random.choice(recipients)
            hospital = random.choice(verified_hospitals)
            bg = random.choice(BLOOD_GROUPS)
            urgency = random.choice(list(models.UrgencyEnum))
            is_history = i < 6
            # history = old requests; 'live' ones are recent so they are not past their expiry window
            created = datetime.utcnow() - (timedelta(days=random.randint(3, 60)) if is_history else timedelta(hours=random.randint(1, 5)))
            req = models.BloodRequest(
                requester_id=requester.id, hospital_id=hospital.id, blood_group=bg,
                units_required=random.randint(1, 3), urgency=urgency,
                status=random.choice(statuses_history) if is_history else models.RequestStatusEnum.request_sent,
                created_at=created,
                fulfilled_at=created + timedelta(hours=random.randint(2, 48)) if is_history else None,
                notes="Seed sample request",
                patient_name="Sample Patient", contact_name=requester.full_name,
                contact_phone="+919800000000", ward_info="Ward 3, Bed 12",
            )
            db.add(req)
            db.flush()

            candidates = random.sample(donors, k=min(5, len(donors)))
            for d in candidates:
                resp = random.choice([models.ResponseEnum.accepted, models.ResponseEnum.declined]) if is_history \
                    else models.ResponseEnum.pending
                db.add(models.DonorResponse(
                    request_id=req.id, donor_id=d.id,
                    match_score=round(random.uniform(0.3, 0.95), 3),
                    distance_km=round(random.uniform(1, 40), 2),
                    response=resp,
                    notified_at=created,
                    responded_at=created + timedelta(hours=1) if resp != models.ResponseEnum.pending else None,
                ))
                if req.status == models.RequestStatusEnum.fulfilled and resp == models.ResponseEnum.accepted:
                    db.add(models.DonationHistory(donor_id=d.id, request_id=req.id, hospital_id=hospital.id,
                                                  donation_date=created.date(), units_donated=1))

        db.commit()
        print("Seed complete:")
        print(f"  1 admin      -> admin@bloodlink.dev / Admin@1234")
        print(f"  {len(donors)} donors    -> donor1@bloodlink.dev .. donor{len(donors)}@bloodlink.dev / Donor@1234")
        print(f"  {len(recipients)} recipients -> recipient1@bloodlink.dev .. / Recipient@1234")
        print(f"  {len(hospitals)} hospitals ({len(verified_hospitals)} verified)")
        print("  10 sample blood requests with donor response history")
        print("\nThis is DEVELOPMENT seed data only - do not use in production.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
