from tests.conftest import register_and_login


def admin_headers(client):
    data = register_and_login(client, role="admin", email="bradmin@test.dev", phone="+916660001111")
    return {"Authorization": f"Bearer {data['access_token']}"}


def make_verified_hospital(client):
    headers = admin_headers(client)
    r = client.post("/hospitals", json={
        "name": "BR Test Hospital", "address": "10 Main Rd", "city": "Amritsar",
        "latitude": 31.63, "longitude": 74.87, "contact": "+911112223334",
    }, headers=headers)
    hospital = r.json()
    client.put(f"/admin/hospitals/{hospital['id']}/verify", headers=headers)
    return hospital


def test_create_request_rejects_unverified_hospital(client):
    admin_h = admin_headers(client)
    unverified = client.post("/hospitals", json={
        "name": "Unverified Hosp", "address": "X", "city": "Delhi",
        "latitude": 28.7, "longitude": 77.1, "contact": "+919998887776",
    }, headers=admin_h).json()

    recipient = register_and_login(client, role="recipient", email="brrecipient@test.dev", phone="+916660002222")
    headers = {"Authorization": f"Bearer {recipient['access_token']}"}

    r = client.post("/blood-requests", json={
        "hospital_id": unverified["id"], "blood_group": "O+", "units_required": 2, "patient_name": "Test Patient", "contact_name": "Test Contact", "contact_phone": "+919876543210", "urgency": "high",
    }, headers=headers)
    assert r.status_code == 400


def test_create_and_fetch_request(client):
    hospital = make_verified_hospital(client)
    recipient = register_and_login(client, role="recipient", email="brrecipient2@test.dev", phone="+916660003333")
    headers = {"Authorization": f"Bearer {recipient['access_token']}"}

    r = client.post("/blood-requests", json={
        "hospital_id": hospital["id"], "blood_group": "A+", "units_required": 1, "patient_name": "Test Patient", "contact_name": "Test Contact", "contact_phone": "+919876543210", "urgency": "critical",
    }, headers=headers)
    assert r.status_code == 201
    req = r.json()
    assert req["status"] == "hospital_selected"

    got = client.get(f"/blood-requests/{req['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["blood_group"] == "A+"


def test_recipient_cannot_view_others_request(client):
    hospital = make_verified_hospital(client)
    r1 = register_and_login(client, role="recipient", email="owner@test.dev", phone="+916660004444")
    r2 = register_and_login(client, role="recipient", email="stranger@test.dev", phone="+916660005555")
    h1 = {"Authorization": f"Bearer {r1['access_token']}"}
    h2 = {"Authorization": f"Bearer {r2['access_token']}"}

    created = client.post("/blood-requests", json={
        "hospital_id": hospital["id"], "blood_group": "B-", "units_required": 1, "patient_name": "Test Patient", "contact_name": "Test Contact", "contact_phone": "+919876543210", "urgency": "medium",
    }, headers=h1).json()

    denied = client.get(f"/blood-requests/{created['id']}", headers=h2)
    assert denied.status_code == 403
