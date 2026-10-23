import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Use a separate SQLite test database so the test-suite is self-contained and
# fast, and never touches the real MySQL dev/prod database. The application
# code itself is fully MySQL-targeted (see app/database.py); swapping the
# engine here is standard SQLAlchemy test practice and exercises the same
# ORM models, routes, services and ML pipeline end-to-end.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_bloodlink.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

TEST_DB_FILE = Path(__file__).resolve().parent.parent / "test_bloodlink.db"

engine = create_engine("sqlite:///./test_bloodlink.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    return TestClient(app)


def register_and_login(client, role="recipient", email=None, phone=None):
    email = email or f"{role}_{os.urandom(3).hex()}@test.dev"
    phone = phone or f"+91{os.urandom(4).hex()}"
    if role == "admin":
        # Admins cannot self-register through the API (by design) - create directly.
        from app import models
        from app.security import hash_password
        db = TestingSessionLocal()
        db.add(models.User(full_name="Test Admin", email=email, phone=phone,
                           password_hash=hash_password("TestPass123"), role=models.RoleEnum.admin,
                           is_phone_verified=True))
        db.commit(); db.close()
        r = client.post("/auth/login", json={"email": email, "password": "TestPass123"})
        assert r.status_code == 200, r.text
        return r.json()
    r = client.post("/auth/register", json={
        "full_name": f"Test {role.title()}",
        "email": email, "phone": phone, "password": "TestPass123", "role": role,
    })
    assert r.status_code == 201, r.text
    return r.json()
