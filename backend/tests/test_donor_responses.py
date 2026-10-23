from datetime import datetime, timedelta
from tests.conftest import register_and_login, TestingSessionLocal
from app import models


def admin_headers(client, n="1"):
    data = register_and_login(client, role="admin", email=f"dradmin{n}@test.dev", phone=f"+91888000{n}111")
    return {"Authorization": f"Bearer {data['access_token']}"}


def setup_world(client, urgency="critical", tag="a"):
    admin_h = admin_headers(client, tag)
    hospital = client.post("/hospitals", json={
        "name": "DR Test Hospital", "address": "1 Rd", "city": "Amritsar",
        "latitude": 31.63, "longitude": 74.87, "contact": "+919990001112",
    }, headers=admin_h).json()
    client.put(f"/admin/hospitals/{hospital['id']}/verify", headers=admin_h)

    d = register_and_login(client, role="donor", email=f"drdonor{tag}@test.dev", phone=f"+91888{tag}002222")
    dh = {"Authorization": f"Bearer {d['access_token']}"}
    donor = client.post("/donors", json={"blood_group": "O-", "age": 30, "city": "Amritsar",
                        "latitude": 31.63, "longitude": 74.87, "is_available": True}, headers=dh).json()

    r = register_and_login(client, role="recipient", email=f"drrec{tag}@test.dev", phone=f"+91888{tag}003333")
    rh = {"Authorization": f"Bearer {r['access_token']}"}
    req = client.post("/blood-requests", json={"hospital_id": hospital["id"], "blood_group": "O-",
                      "units_required": 1, "patient_name": "Test Patient", "contact_name": "Test Contact", "contact_phone": "+919876543210", "urgency": urgency}, headers=rh).json()
    return admin_h, hospital, donor, dh, rh, req


def test_full_workflow_donor_accepts(client):
    _, _, donor, dh, rh, req = setup_world(client, tag="1")

    match = client.post(f"/match-donors/{req['id']}", headers=rh).json()
    assert match["total_eligible_donors"] == 1

    sent = client.post(f"/match-donors/{req['id']}/send", json={"donor_ids": [donor["id"]]}, headers=rh)
    assert sent.status_code == 200, sent.text
    assert sent.json()["sent_to"] == [donor["id"]]
    assert sent.json()["status"] == "request_sent"

    notes = client.get("/notifications", headers=dh).json()
    assert any(n["type"] == "match_request" for n in notes)

    # sending again to the same donor is refused (no duplicate pings)
    again = client.post(f"/match-donors/{req['id']}/send", json={"donor_ids": [donor["id"]]}, headers=rh)
    assert again.status_code == 400

    resp = client.post("/donor-responses", json={"request_id": req["id"], "donor_id": donor["id"],
                       "response": "accepted"}, headers=dh)
    assert resp.status_code == 200 and resp.json()["response"] == "accepted"

    dup = client.post("/donor-responses", json={"request_id": req["id"], "donor_id": donor["id"],
                      "response": "declined"}, headers=dh)
    assert dup.status_code == 400

    # re-running matching after acceptance must NOT regress the status
    client.post(f"/match-donors/{req['id']}", headers=rh)
    assert client.get(f"/blood-requests/{req['id']}", headers=rh).json()["status"] == "donor_accepted"

    done = client.put(f"/blood-requests/{req['id']}", json={"status": "fulfilled"}, headers=rh)
    assert done.status_code == 200 and done.json()["status"] == "fulfilled"

    me = client.get("/donors/me", headers=dh).json()
    assert me["total_donations"] == 1
    hist = client.get("/donors/me/history", headers=dh).json()
    assert len(hist) == 1 and hist[0]["request_id"] == req["id"]


def test_cannot_fulfil_before_a_donor_accepts(client):
    *_, rh, req = setup_world(client, tag="2")
    r = client.put(f"/blood-requests/{req['id']}", json={"status": "fulfilled"}, headers=rh)
    assert r.status_code == 400
    r = client.put(f"/blood-requests/{req['id']}", json={"status": "donor_accepted"}, headers=rh)
    assert r.status_code == 400   # users can't fake pipeline statuses


def test_decline_notifies_recipient_and_keeps_request_open(client):
    _, _, donor, dh, rh, req = setup_world(client, tag="3")
    client.post(f"/match-donors/{req['id']}/send", json={"donor_ids": [donor["id"]]}, headers=rh)
    r = client.post("/donor-responses", json={"request_id": req["id"], "donor_id": donor["id"],
                    "response": "declined"}, headers=dh)
    assert r.status_code == 200
    assert client.get(f"/blood-requests/{req['id']}", headers=rh).json()["status"] == "request_sent"
    assert any(n["type"] == "donor_decline" for n in client.get("/notifications", headers=rh).json())


def test_expired_request_blocks_matching_and_responses(client):
    _, _, donor, dh, rh, req = setup_world(client, urgency="critical", tag="4")
    client.post(f"/match-donors/{req['id']}/send", json={"donor_ids": [donor["id"]]}, headers=rh)

    # age the request beyond the 24h critical window
    db = TestingSessionLocal()
    row = db.query(models.BloodRequest).filter(models.BloodRequest.id == req["id"]).first()
    row.created_at = datetime.utcnow() - timedelta(hours=30)
    db.commit(); db.close()

    assert client.post(f"/match-donors/{req['id']}", headers=rh).status_code == 410
    r = client.post("/donor-responses", json={"request_id": req["id"], "donor_id": donor["id"],
                    "response": "accepted"}, headers=dh)
    assert r.status_code == 410
    assert client.get(f"/blood-requests/{req['id']}", headers=rh).json()["status"] == "expired"


def test_donor_cannot_answer_for_someone_else(client):
    _, _, donor, dh, rh, req = setup_world(client, tag="5")
    d2 = register_and_login(client, role="donor", email="other_d@test.dev", phone="+918889990001")
    h2 = {"Authorization": f"Bearer {d2['access_token']}"}
    client.post("/donors", json={"blood_group": "O-", "age": 26, "city": "Amritsar",
                "latitude": 31.64, "longitude": 74.88, "is_available": True}, headers=h2)
    r = client.post("/donor-responses", json={"request_id": req["id"], "donor_id": donor["id"],
                    "response": "accepted"}, headers=h2)
    assert r.status_code == 403
