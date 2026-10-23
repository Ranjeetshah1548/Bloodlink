"""
End-to-end verification against a RUNNING server + real database.

    python scripts/e2e_check.py --base http://localhost:8000 --otp-log /path/to/uvicorn.log

Requires `python seed.py` to have been run (uses admin@bloodlink.dev).
Creates throw-away users with random emails, so it is safe to re-run.
--otp-log is optional: if given, the OTP printed by the console provider is
read from the server log and the phone-verification step is exercised too.
"""
import argparse, os, re, sys, time
import requests

ap = argparse.ArgumentParser()
ap.add_argument("--base", default="http://localhost:8000")
ap.add_argument("--otp-log", default=None)
a = ap.parse_args()
B = a.base.rstrip("/")
tag = os.urandom(3).hex()
passed = 0

def check(cond, msg):
    global passed
    if not cond:
        print(f"  FAIL  {msg}"); sys.exit(1)
    passed += 1; print(f"  ok    {msg}")

def H(tok): return {"Authorization": f"Bearer {tok}"}
def call(m, path, tok=None, **kw):
    return requests.request(m, B + path, headers=H(tok) if tok else None, timeout=30, **kw)

print("== auth & roles ==")
check(call("GET", "/health").json()["status"] == "healthy", "API healthy")
r = call("POST", "/auth/register", json={"full_name": "Sneaky", "email": f"s{tag}@x.dev", "phone": f"+9100{tag}1", "password": "Password123", "role": "admin"})
check(r.status_code == 422, "self-registering as admin is rejected")
admin = call("POST", "/auth/login", json={"email": "admin@bloodlink.dev", "password": "Admin@1234"}).json()["access_token"]
check(call("GET", "/admin/users", admin).status_code == 200, "admin can list users")

phone_d = f"+91777{tag}1"
d = call("POST", "/auth/register", json={"full_name": "E2E Donor", "email": f"d{tag}@e2e.dev", "phone": phone_d, "password": "Password123", "role": "donor"})
check(d.status_code == 201, "donor registers"); dtok = d.json()["access_token"]
check(call("GET", "/admin/users", dtok).status_code == 403, "donor blocked from admin API")
if a.otp_log:
    time.sleep(0.5)
    codes = re.findall(rf"Sending code (\d+) to {re.escape(phone_d)}", open(a.otp_log).read())
    check(bool(codes), "OTP delivered via console provider")
    check(call("POST", "/auth/verify-otp", json={"phone": phone_d, "code": "000000"}).status_code == 400, "wrong OTP rejected")
    check(call("POST", "/auth/verify-otp", json={"phone": phone_d, "code": codes[-1]}).status_code == 200, "correct OTP verifies phone")
r = call("POST", "/auth/register", json={"full_name": "E2E Recipient", "email": f"r{tag}@e2e.dev", "phone": f"+91666{tag}1", "password": "Password123", "role": "recipient"})
rtok = r.json()["access_token"]

print("== hospitals / map data ==")
hosp = call("GET", "/hospitals", params={"lat": 31.63, "lng": 74.87}).json()
check(len(hosp) >= 1 and all(h["is_verified"] for h in hosp), f"{len(hosp)} verified hospitals returned")
check(all(h["distance_km"] is not None for h in hosp) and hosp == sorted(hosp, key=lambda h: h["distance_km"]), "hospitals sorted by distance from user")
h0 = hosp[0]
allh = call("GET", "/admin/hospitals", admin).json()
unv = [h for h in allh if not h["is_verified"]]
if unv:
    r = call("POST", "/blood-requests", rtok, json={"hospital_id": unv[0]["id"], "blood_group": "A+", "units_required": 1, "patient_name": "Test Patient", "contact_name": "Test Contact", "contact_phone": "+919876543210", "urgency": "high"})
    check(r.status_code == 400, "request against UNVERIFIED hospital refused")
check(call("POST", "/blood-requests", rtok, json={"hospital_id": 999999, "blood_group": "A+", "units_required": 1, "patient_name": "Test Patient", "contact_name": "Test Contact", "contact_phone": "+919876543210", "urgency": "high"}).status_code == 404, "request against nonexistent hospital refused")

print("== donor profile ==")
prof = call("POST", "/donors", dtok, json={"blood_group": "A-", "age": 29, "city": h0["city"], "latitude": h0["latitude"] + 0.01, "longitude": h0["longitude"], "is_available": True})
check(prof.status_code == 201, "donor profile created"); did = prof.json()["id"]

print("== request -> compatibility -> ML ranking ==")
req = call("POST", "/blood-requests", rtok, json={"hospital_id": h0["id"], "blood_group": "A+", "units_required": 1, "patient_name": "Test Patient", "contact_name": "Test Contact", "contact_phone": "+919876543210", "urgency": "critical"}).json()
check(req["status"] == "hospital_selected", "request created at hospital_selected")
m = call("POST", f"/match-donors/{req['id']}", rtok).json()
check(set(m["eligible_blood_groups"]) == {"A+", "A-", "O+", "O-"}, "A+ compatibility rules correct")
groups = {x["blood_group"] for x in m["ranked_donors"]}
check(groups <= {"A+", "A-", "O+", "O-"}, "no incompatible blood group in results")
ours = [x for x in m["ranked_donors"] if x["donor_id"] == did]
check(len(ours) == 1 and ours[0]["distance_km"] < 3, "new nearby donor ranked, distance computed")
sc = [x["response_likelihood"] for x in m["ranked_donors"]]
check(all(0 <= s <= 1 for s in sc) and sc == sorted(sc, reverse=True), f"{len(sc)} donors ranked by RF likelihood (desc)")
check(call("GET", "/notifications", dtok).json() == [], "matching alone notifies nobody")
check(call("GET", f"/blood-requests/{req['id']}", dtok).status_code == 403, "donor not contacted cannot open the request")

print("== send -> respond -> fulfil ==")
s = call("POST", f"/match-donors/{req['id']}/send", rtok, json={"donor_ids": [did]})
check(s.status_code == 200 and s.json()["status"] == "request_sent", "recipient sends request to chosen donor")
check(any(n["type"] == "match_request" for n in call("GET", "/notifications", dtok).json()), "donor notification stored in MySQL")
check(call("GET", "/donor-responses/my", dtok).json()[0]["response"] == "pending", "donor sees pending request")
PH = "+919876543210"
pre = call("GET", f"/blood-requests/{req['id']}", dtok).json()
check(pre["contact_visible"] is False and pre["contact_phone"] is None and pre["patient_name"] is None, "PRIVACY: donor sees no contact/patient details before accepting")
check(PH not in call("GET", "/blood-requests", dtok).text and PH not in call("GET", "/notifications", dtok).text, "PRIVACY: phone absent from donor's list + notifications")
check(all(x["phone"] is None for x in call("GET", f"/blood-requests/{req['id']}/responders", rtok).json()), "seeker sees no donor phone before accept")
r = call("POST", "/donor-responses", dtok, json={"request_id": req["id"], "donor_id": did, "response": "accepted"})
check(r.status_code == 200, "donor accepts")
check(call("GET", f"/blood-requests/{req['id']}", rtok).json()["status"] == "donor_accepted", "recipient sees live status: donor_accepted")
post = call("GET", f"/blood-requests/{req['id']}", dtok).json()
check(post["contact_visible"] and post["contact_phone"] == PH and post["patient_name"] == "Test Patient" and post["hospital_contact"], "after accept: donor receives patient + seeker contact + hospital contact")
resp = call("GET", f"/blood-requests/{req['id']}/responders", rtok).json()
check(any(x["donor_id"] == did and x["phone"] == phone_d for x in resp), "after accept: seeker receives the accepted donor's phone")
call("POST", f"/match-donors/{req['id']}", rtok)
check(call("GET", f"/blood-requests/{req['id']}", rtok).json()["status"] == "donor_accepted", "re-running matching does not regress status")
check(call("PUT", f"/blood-requests/{req['id']}", rtok, json={"status": "fulfilled"}).json()["status"] == "fulfilled", "request fulfilled")
check(call("GET", "/donors/me", dtok).json()["total_donations"] == 1, "donor total_donations incremented")
check(len(call("GET", "/donors/me/history", dtok).json()) == 1, "donation_history row stored")
check(call("PUT", f"/blood-requests/{req['id']}", rtok, json={"status": "closed"}).status_code == 400, "finished request cannot be modified")

print("== recovery rules ==")
r = call("POST", f"/match-donors/{req['id']}", rtok)
check(r.status_code == 400, "matching on a fulfilled request refused")
check(call("PUT", "/donors/availability", dtok, json={"is_available": False}).json()["is_available"] is False, "donor toggles availability off")
req2 = call("POST", "/blood-requests", rtok, json={"hospital_id": h0["id"], "blood_group": "A+", "units_required": 1, "patient_name": "Test Patient", "contact_name": "Test Contact", "contact_phone": "+919876543210", "urgency": "low"}).json()
m2 = call("POST", f"/match-donors/{req2['id']}", rtok).json()
check(did not in [x["donor_id"] for x in m2["ranked_donors"]], "unavailable donor excluded")

print("== reports & admin ==")
rep = call("POST", "/reports", rtok, json={"request_id": req["id"], "reason": "Other", "description": "e2e"})
check(rep.status_code == 201, "report filed")
check(call("PUT", f"/admin/reports/{rep.json()['id']}", admin, json={"status": "resolved"}).json()["status"] == "resolved", "admin resolves report")
uid = call("POST", "/auth/login", json={"email": f"d{tag}@e2e.dev", "password": "Password123"}).json()["user_id"]
check(call("PUT", f"/admin/users/{uid}/active", admin, json={"is_active": False}).status_code == 200, "admin deactivates user")
check(call("GET", "/notifications", dtok).status_code == 401, "deactivated user's token stops working")
out = call("POST", "/auth/logout", rtok)
check(out.status_code == 200 and call("GET", "/notifications", rtok).status_code == 401, "logout revokes token")
print(f"\nALL {passed} CHECKS PASSED")
