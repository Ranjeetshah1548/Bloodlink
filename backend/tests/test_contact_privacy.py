"""Contact details must reach a donor ONLY after that donor accepts."""
from tests.conftest import register_and_login

PHONE = "+919812345678"


def world(client, tag):
    a = register_and_login(client, role="admin", email=f"cp_admin{tag}@t.dev", phone=f"+9177{tag}0001")
    ah = {"Authorization": f"Bearer {a['access_token']}"}
    hosp = client.post("/hospitals", json={"name": "Privacy Hosp", "address": "9 Rd", "city": "Amritsar",
                       "latitude": 31.63, "longitude": 74.87, "contact": "+911800111222"}, headers=ah).json()
    client.put(f"/admin/hospitals/{hosp['id']}/verify", headers=ah)

    def donor(n):
        d = register_and_login(client, role="donor", email=f"cp_d{n}{tag}@t.dev", phone=f"+9166{tag}00{n}")
        h = {"Authorization": f"Bearer {d['access_token']}"}
        prof = client.post("/donors", json={"blood_group": "O-", "age": 30, "city": "Amritsar",
                           "latitude": 31.63, "longitude": 74.87, "is_available": True}, headers=h).json()
        return prof, h, d
    r = register_and_login(client, role="recipient", email=f"cp_r{tag}@t.dev", phone=f"+9155{tag}0001")
    rh = {"Authorization": f"Bearer {r['access_token']}"}
    return hosp, donor, rh


def make_request(client, hosp, rh, **extra):
    body = {"hospital_id": hosp["id"], "blood_group": "O-", "units_required": 2, "urgency": "high",
            "patient_name": "Ramesh Kumar", "contact_name": "Sunita Kumar", "contact_phone": PHONE,
            "ward_info": "ICU, Bed 4", "notes": "Call on arrival", **extra}
    return client.post("/blood-requests", json=body, headers=rh)


def test_contact_fields_are_required(client):
    hosp, _, rh = world(client, "11")
    r = client.post("/blood-requests", json={"hospital_id": hosp["id"], "blood_group": "O-",
                    "units_required": 1, "urgency": "low"}, headers=rh)
    assert r.status_code == 422
    bad = make_request(client, hosp, rh, contact_phone="abc")
    assert bad.status_code == 422


def test_requester_sees_own_contact_fields(client):
    hosp, _, rh = world(client, "12")
    req = make_request(client, hosp, rh).json()
    got = client.get(f"/blood-requests/{req['id']}", headers=rh).json()
    assert got["patient_name"] == "Ramesh Kumar" and got["contact_phone"] == PHONE and got["ward_info"] == "ICU, Bed 4"


def test_donor_sees_no_contact_until_accept(client):
    hosp, donor, rh = world(client, "13")
    prof, dh, _ = donor(1)
    req = make_request(client, hosp, rh).json()
    client.post(f"/match-donors/{req['id']}/send", json={"donor_ids": [prof["id"]]}, headers=rh)

    # --- before accepting: list + detail both hide every contact-bearing field
    for view in (client.get("/blood-requests", headers=dh).json()[0],
                 client.get(f"/blood-requests/{req['id']}", headers=dh).json()):
        assert view["contact_visible"] is False and view["my_response"] == "pending"
        assert view["hospital_name"] == "Privacy Hosp"           # non-sensitive info is shown
        for k in ("contact_phone", "contact_name", "patient_name", "ward_info", "hospital_contact", "notes"):
            assert view[k] is None, k
        assert PHONE not in str(view)
    # notification text must not leak the phone either
    assert all(PHONE not in n["message"] for n in client.get("/notifications", headers=dh).json())

    # --- a declined donor never gets contact details
    client.post("/donor-responses", json={"request_id": req["id"], "donor_id": prof["id"], "response": "declined"}, headers=dh)
    v = client.get(f"/blood-requests/{req['id']}", headers=dh).json()
    assert v["contact_visible"] is False and v["contact_phone"] is None


def test_contact_released_after_accept_only_to_that_donor(client):
    hosp, donor, rh = world(client, "14")
    p1, h1, _ = donor(1)
    p2, h2, _ = donor(2)
    req = make_request(client, hosp, rh).json()
    client.post(f"/match-donors/{req['id']}/send", json={"donor_ids": [p1["id"], p2["id"]]}, headers=rh)

    client.post("/donor-responses", json={"request_id": req["id"], "donor_id": p1["id"], "response": "accepted"}, headers=h1)
    acc = client.get(f"/blood-requests/{req['id']}", headers=h1).json()
    assert acc["contact_visible"] is True
    assert acc["contact_phone"] == PHONE and acc["contact_name"] == "Sunita Kumar"
    assert acc["patient_name"] == "Ramesh Kumar" and acc["ward_info"] == "ICU, Bed 4"
    assert acc["hospital_contact"] == "+911800111222" and acc["notes"] == "Call on arrival"

    # the OTHER donor (still pending) must still see nothing
    other = client.get(f"/blood-requests/{req['id']}", headers=h2).json()
    assert other["contact_visible"] is False and other["contact_phone"] is None


def test_donor_cannot_open_request_they_were_not_contacted_for(client):
    hosp, donor, rh = world(client, "15")
    _, dh, _ = donor(1)
    req = make_request(client, hosp, rh).json()
    assert client.get(f"/blood-requests/{req['id']}", headers=dh).status_code == 403
    assert client.get("/blood-requests", headers=dh).json() == []


def test_requester_sees_donor_phone_only_after_accept(client):
    hosp, donor, rh = world(client, "16")
    p1, h1, d1 = donor(1)
    p2, h2, _ = donor(2)
    req = make_request(client, hosp, rh).json()
    client.post(f"/match-donors/{req['id']}/send", json={"donor_ids": [p1["id"], p2["id"]]}, headers=rh)
    rows = client.get(f"/blood-requests/{req['id']}/responders", headers=rh).json()
    assert len(rows) == 2 and all(r["phone"] is None and r["response"] == "pending" for r in rows)

    client.post("/donor-responses", json={"request_id": req["id"], "donor_id": p1["id"], "response": "accepted"}, headers=h1)
    rows = {r["donor_id"]: r for r in client.get(f"/blood-requests/{req['id']}/responders", headers=rh).json()}
    assert rows[p1["id"]]["phone"] and rows[p1["id"]]["response"] == "accepted"
    assert rows[p2["id"]]["phone"] is None

    # responders list is not available to donors or to other recipients
    assert client.get(f"/blood-requests/{req['id']}/responders", headers=h1).status_code == 403
    other = register_and_login(client, role="recipient", email="cp_other@t.dev", phone="+915500099999")
    assert client.get(f"/blood-requests/{req['id']}/responders",
                      headers={"Authorization": f"Bearer {other['access_token']}"}).status_code == 403


def test_auth_me(client):
    d = register_and_login(client, role="recipient", email="me@t.dev", phone="+915500088888")
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {d['access_token']}"}).json()
    assert me["email"] == "me@t.dev" and me["phone"] == "+915500088888"
