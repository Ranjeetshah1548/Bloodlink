"""
Create an admin account (admins can't self-register through the API).

    python create_admin.py --email you@example.com --name "Your Name" --phone +911234567890
(prompts for the password; or set ADMIN_PASSWORD in the environment)
"""
import argparse, getpass, os, sys
from app.database import SessionLocal, Base, engine
from app import models
from app.security import hash_password

ap = argparse.ArgumentParser()
ap.add_argument("--email", required=True)
ap.add_argument("--name", default="Administrator")
ap.add_argument("--phone", required=True)
a = ap.parse_args()

pw = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Admin password (min 8 chars): ")
if len(pw) < 8:
    sys.exit("Password must be at least 8 characters.")

Base.metadata.create_all(bind=engine)
db = SessionLocal()
if db.query(models.User).filter((models.User.email == a.email) | (models.User.phone == a.phone)).first():
    sys.exit("A user with that email/phone already exists.")
db.add(models.User(full_name=a.name, email=a.email, phone=a.phone,
                   password_hash=hash_password(pw), role=models.RoleEnum.admin, is_phone_verified=True))
db.commit()
print(f"Admin {a.email} created.")
