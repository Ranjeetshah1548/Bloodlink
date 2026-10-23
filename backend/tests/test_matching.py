from tests.conftest import register_and_login


def admin_headers(client):
    data = register_and_login(client, role="admin", email="madmin@test.dev", phone="+917770001111")
    return {"Authorization": f"Bearer {data['access_token']}"}


def make_verified_hospital(client, lat=31.63, lng=74.87):
    headers = admin_headers(client)
    r = client.post("/hospitals", json={
        "name": "Match Test Hospital", "address": "20 Care Blvd", "city": "Amritsar",
        "latitude": lat, "longitude": lng, "contact": "+911112223335",
    }, headers=headers)
    hospital = r.json()
    client.put(f"/admin/hospitals/{hospital['id']}/verify", headers=headers)
    return hospital


def make_donor(client, blood_group, lat, lng, email, phone, available=True):
    data = register_and_login(client, role="donor", email=email, phone=phone)
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    r = client.post("/donors", json={
        "blood_group": blood_group, "age": 28, "city": "Amritsar",
        "latitude": lat, "longitude": lng, "is_available": available,
    }, headers=headers)
    assert r.status_code == 201, r.text
    return r.json(), headers


def test_incompatible_donor_excluded_from_matching(client):
    hospital = make_verified_hospital(client)
    # AB- donor cannot donate to an O+ recipient
    make_donor(client, "AB-", 31.63, 74.87, "abneg@test.dev", "+917770002222")
    # O- donor CAN donate to anyone
    make_donor(client, "O-", 31.635, 74.875, "oneg@test.dev", "+917770003333")

    recipient = register_and_login(client, role="recipient", email="mrecipient@test.dev", phone="+917770004444")
    headers = {"Authorization": f"Bearer {recipient['access_token']}"}
    req = client.post("/blood-requests", json={
        "hospital_id": hospital["id"], "blood_group": "O+", "units_required": 1, "patient_name": "Test Patient", "contact_name": "Test Contact", "contact_phone": "+919876543210", "urgency": "high",
    }, headers=headers).json()

    result = client.post(f"/match-donors/{req['id']}", headers=headers)
    assert result.status_code == 200
    body = result.json()
    assert "AB-" not in body["eligible_blood_groups"]
    assert "O-" in body["eligible_blood_groups"]
    groups_returned = {d["blood_group"] for d in body["ranked_donors"]}
    assert "AB-" not in groups_returned


def test_ranked_donors_ordered_by_score_then_distance(client):
    hospital = make_verified_hospital(client, lat=31.63, lng=74.87)
    # Two compatible O+ donors at different distances
    make_donor(client, "O+", 31.631, 74.871, "near@test.dev", "+917770005555")   # very close
    make_donor(client, "O+", 32.50, 75.80, "far@test.dev", "+917770006666")      # far away

    recipient = register_and_login(client, role="recipient", email="mrecipient2@test.dev", phone="+917770007777")
    headers = {"Authorization": f"Bearer {recipient['access_token']}"}
    req = client.post("/blood-requests", json={
        "hospital_id": hospital["id"], "blood_group": "O+", "units_required": 1, "patient_name": "Test Patient", "contact_name": "Test Contact", "contact_phone": "+919876543210", "urgency": "medium",
    }, headers=headers).json()

    result = client.post(f"/match-donors/{req['id']}", headers=headers).json()
    assert result["total_eligible_donors"] >= 2
    distances = [d["distance_km"] for d in result["ranked_donors"]]
    scores = [d["response_likelihood"] for d in result["ranked_donors"]]
    # every score is a valid probability
    assert all(0.0 <= s <= 1.0 for s in scores)
    # ranking contract: descending score, ties broken by ascending distance
    pairs = list(zip(scores, distances))
    assert pairs == sorted(pairs, key=lambda p: (-p[0], p[1]))
    # the donor 1km away must outrank the donor ~120km away
    assert distances[0] < distances[-1]


def test_unavailable_donor_excluded(client):
    hospital = make_verified_hospital(client)
    make_donor(client, "O-", 31.63, 74.87, "unavail@test.dev", "+917770008888", available=False)

    recipient = register_and_login(client, role="recipient", email="mrecipient3@test.dev", phone="+917770009999")
    headers = {"Authorization": f"Bearer {recipient['access_token']}"}
    req = client.post("/blood-requests", json={
        "hospital_id": hospital["id"], "blood_group": "O-", "units_required": 1, "patient_name": "Test Patient", "contact_name": "Test Contact", "contact_phone": "+919876543210", "urgency": "low",
    }, headers=headers).json()

    result = client.post(f"/match-donors/{req['id']}", headers=headers).json()
    assert result["total_eligible_donors"] == 0


def test_matching_does_not_notify_until_recipient_sends(client):
    hospital = make_verified_hospital(client)
    _, dh = make_donor(client, "O-", 31.63, 74.87, "quiet@test.dev", "+917771110001")
    recipient = register_and_login(client, role="recipient", email="quiet_r@test.dev", phone="+917771110002")
    headers = {"Authorization": f"Bearer {recipient['access_token']}"}
    req = client.post("/blood-requests", json={"hospital_id": hospital["id"], "blood_group": "O-",
                      "units_required": 1, "patient_name": "Test Patient", "contact_name": "Test Contact", "contact_phone": "+919876543210", "urgency": "high"}, headers=headers).json()
    m = client.post(f"/match-donors/{req['id']}", headers=headers).json()
    assert m["total_eligible_donors"] == 1
    assert client.get("/notifications", headers=dh).json() == []          # nothing sent yet
    assert client.get(f"/blood-requests/{req['id']}", headers=headers).json()["status"] == "donors_ranked"


def test_send_rejects_incompatible_or_unknown_donor(client):
    hospital = make_verified_hospital(client)
    abneg, _ = make_donor(client, "AB-", 31.63, 74.87, "ab2@test.dev", "+917771110003")
    recipient = register_and_login(client, role="recipient", email="send_r@test.dev", phone="+917771110004")
    headers = {"Authorization": f"Bearer {recipient['access_token']}"}
    req = client.post("/blood-requests", json={"hospital_id": hospital["id"], "blood_group": "O+",
                      "units_required": 1, "patient_name": "Test Patient", "contact_name": "Test Contact", "contact_phone": "+919876543210", "urgency": "high"}, headers=headers).json()
    # AB- is medically incompatible with O+; the server must refuse even if the client asks.
    r = client.post(f"/match-donors/{req['id']}/send", json={"donor_ids": [abneg["id"]]}, headers=headers)
    assert r.status_code == 400


def test_donor_cannot_run_matching(client):
    hospital = make_verified_hospital(client)
    _, dh = make_donor(client, "O-", 31.63, 74.87, "dm@test.dev", "+917771110005")
    recipient = register_and_login(client, role="recipient", email="dm_r@test.dev", phone="+917771110006")
    rh = {"Authorization": f"Bearer {recipient['access_token']}"}
    req = client.post("/blood-requests", json={"hospital_id": hospital["id"], "blood_group": "O-",
                      "units_required": 1, "patient_name": "Test Patient", "contact_name": "Test Contact", "contact_phone": "+919876543210", "urgency": "low"}, headers=rh).json()
    assert client.post(f"/match-donors/{req['id']}", headers=dh).status_code == 403
