from tests.conftest import register_and_login


def make_admin_headers(client):
    data = register_and_login(client, role="admin", email="hospadmin@test.dev", phone="+915550001111")
    return {"Authorization": f"Bearer {data['access_token']}"}


def test_create_hospital_requires_admin(client):
    donor = register_and_login(client, role="donor", email="hospdonor@test.dev", phone="+915550002222")
    headers = {"Authorization": f"Bearer {donor['access_token']}"}
    r = client.post("/hospitals", json={
        "name": "Unauthorized Hospital", "address": "1 Test St", "city": "Amritsar",
        "latitude": 31.63, "longitude": 74.87, "contact": "+911234567890",
    }, headers=headers)
    assert r.status_code == 403


def test_hospital_unverified_by_default_and_admin_can_verify(client):
    headers = make_admin_headers(client)
    r = client.post("/hospitals", json={
        "name": "New Test Hospital", "address": "5 Care Ave", "city": "Amritsar",
        "latitude": 31.64, "longitude": 74.88, "contact": "+911234500000",
    }, headers=headers)
    assert r.status_code == 201
    hospital = r.json()
    assert hospital["is_verified"] is False

    # not visible in default (verified-only) public listing
    listing = client.get("/hospitals")
    ids = [h["id"] for h in listing.json()]
    assert hospital["id"] not in ids

    verify = client.put(f"/admin/hospitals/{hospital['id']}/verify", headers=headers)
    assert verify.status_code == 200
    assert verify.json()["is_verified"] is True

    listing2 = client.get("/hospitals")
    ids2 = [h["id"] for h in listing2.json()]
    assert hospital["id"] in ids2
