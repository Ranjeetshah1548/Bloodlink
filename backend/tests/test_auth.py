from tests.conftest import register_and_login


def test_register_creates_user_and_returns_token(client):
    data = register_and_login(client, role="donor")
    assert "access_token" in data
    assert data["role"] == "donor"


def test_duplicate_email_registration_rejected(client):
    data = register_and_login(client, role="recipient", email="dup@test.dev", phone="+911111111111")
    r = client.post("/auth/register", json={
        "full_name": "Dup Again", "email": "dup@test.dev", "phone": "+912222222222",
        "password": "TestPass123", "role": "recipient",
    })
    assert r.status_code == 409


def test_login_success_and_wrong_password(client):
    email, phone = "loginuser@test.dev", "+913333333333"
    register_and_login(client, role="donor", email=email, phone=phone)

    ok = client.post("/auth/login", json={"email": email, "password": "TestPass123"})
    assert ok.status_code == 200
    assert "access_token" in ok.json()

    bad = client.post("/auth/login", json={"email": email, "password": "WrongPassword"})
    assert bad.status_code == 401


def test_protected_route_requires_token(client):
    r = client.get("/donors/me")
    assert r.status_code in (401, 403)


def test_logout_revokes_token(client):
    data = register_and_login(client, role="donor", email="logoutuser@test.dev", phone="+914444444444")
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r1 = client.get("/notifications", headers=headers)
    assert r1.status_code == 200

    out = client.post("/auth/logout", headers=headers)
    assert out.status_code == 200

    r2 = client.get("/notifications", headers=headers)
    assert r2.status_code == 401


def test_cannot_self_register_as_admin(client):
    r = client.post("/auth/register", json={
        "full_name": "Sneaky", "email": "sneaky@test.dev", "phone": "+915550009999",
        "password": "TestPass123", "role": "admin"})
    assert r.status_code == 422


def test_otp_flow_verifies_phone(client):
    import re
    from tests.conftest import TestingSessionLocal
    from app import models
    from app.services import otp_service
    captured = {}
    otp_service._send_via_console = lambda phone, code: captured.update(code=code)
    register_and_login(client, role="donor", email="otpuser@test.dev", phone="+915551230000")
    assert client.post("/auth/verify-otp", json={"phone": "+915551230000", "code": "000000"}).status_code == 400
    ok = client.post("/auth/verify-otp", json={"phone": "+915551230000", "code": captured["code"]})
    assert ok.status_code == 200
    db = TestingSessionLocal()
    assert db.query(models.User).filter_by(email="otpuser@test.dev").first().is_phone_verified is True
    # code is single-use
    assert client.post("/auth/verify-otp", json={"phone": "+915551230000", "code": captured["code"]}).status_code == 400
    db.close()


def test_deactivated_user_is_locked_out(client):
    admin = register_and_login(client, role="admin", email="deact_admin@test.dev", phone="+915550007001")
    ah = {"Authorization": f"Bearer {admin['access_token']}"}
    victim = register_and_login(client, role="donor", email="victim@test.dev", phone="+915550007002")
    vh = {"Authorization": f"Bearer {victim['access_token']}"}
    assert client.get("/notifications", headers=vh).status_code == 200
    r = client.put(f"/admin/users/{victim['user_id']}/active", json={"is_active": False}, headers=ah)
    assert r.status_code == 200
    assert client.get("/notifications", headers=vh).status_code == 401
    assert client.post("/auth/login", json={"email": "victim@test.dev", "password": "TestPass123"}).status_code == 403
