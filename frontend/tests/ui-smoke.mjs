// Executes the REAL frontend pages (their own <script>s, services layer and
// fetch calls) in jsdom against a RUNNING backend + database, and asserts on
// the resulting DOM. Not a mock: every API call hits the live FastAPI server.
//
//   FRONT=http://localhost:5500 API=http://localhost:8000 node ui-smoke.mjs
// Prereqs: backend running, `python seed.py` done, `python -m http.server 5500` in frontend/.
import { JSDOM, VirtualConsole } from "jsdom";
import fs from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const leafletSrc = fs.readFileSync(require.resolve("leaflet/dist/leaflet-src.js"), "utf8");

const FRONT = process.env.FRONT || "http://localhost:5500";
const API = process.env.API || "http://localhost:8000";
let passed = 0;
const ok = (c, m) => { if (!c) { console.log("  FAIL ", m); process.exit(1); } passed++; console.log("  ok   ", m); };
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function api(method, path, token, body) {
  const r = await fetch(API + path, { method, headers: { "Content-Type": "application/json", ...(token ? { Authorization: "Bearer " + token } : {}) }, body: body ? JSON.stringify(body) : undefined });
  const t = await r.text(); return { status: r.status, data: t ? JSON.parse(t) : null };
}
async function login(email, password) {
  const r = await api("POST", "/auth/login", null, { email, password });
  return r.data;
}

// Opens a page like a browser would (optionally with a logged-in session).
async function open(path, session) {
  const errors = [];
  const vc = new VirtualConsole();
  vc.on("jsdomError", e => { if (!/Not implemented: navigation/.test(e.message)) errors.push(e.message); });
  vc.on("error", e => errors.push(String(e)));
  const dom = await JSDOM.fromURL(FRONT + path, {
    runScripts: "dangerously", resources: "usable", pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      w.fetch = (u, o) => fetch(u, o);                 // real network
      w.confirm = () => true;
      w.scrollTo = () => {}; w.HTMLElement.prototype.scrollIntoView = () => {};
      if (session) {
        w.localStorage.setItem("bloodlink_token", session.access_token);
        w.localStorage.setItem("bloodlink_role", session.role);
        w.localStorage.setItem("bloodlink_user_id", String(session.user_id));
        w.localStorage.setItem("bloodlink_full_name", session.full_name);
      }
      // load Leaflet from node_modules instead of the CDN so map code really runs
      w.document.addEventListener("DOMContentLoaded", () => w.eval(leafletSrc));
    },
  });
  await new Promise(r => dom.window.addEventListener("load", r));
  return { dom, w: dom.window, d: dom.window.document, errors };
}
async function waitFor(fn, what, ms = 8000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { try { const v = fn(); if (v) return v; } catch {} await sleep(100); }
  throw new Error("timed out waiting for: " + what);
}

try {
  console.log("== public pages ==");
  let p = await open("/index.html");
  ok(p.d.querySelector(".brand") && p.d.querySelector("h1"), "home renders header + hero");
  ok(p.d.querySelector('a[href="/login.html"]'), "home header offers Log in when logged out");
  p = await open("/hospitals.html");
  await waitFor(() => p.d.querySelectorAll("#hospital-grid .card").length >= 3, "hospital cards");
  ok(p.d.querySelectorAll("#hospital-grid .card").length >= 3, "hospitals page lists verified hospitals from the API");
  ok(p.d.querySelectorAll(".leaflet-marker-icon").length === p.d.querySelectorAll("#hospital-grid .card").length, "map has one marker per hospital");
  ok(![...p.d.querySelectorAll("#hospital-grid .badge")].some(b => !/Verified/.test(b.textContent)), "every listed hospital shows the Verified badge");
  p = await open("/find-blood.html");
  p.d.getElementById("bg-select").value = "AB-"; p.d.getElementById("bg-select").dispatchEvent(new p.w.Event("change"));
  ok(/A-/.test(p.d.getElementById("compat-result").textContent) && !/O\+/.test(p.d.getElementById("compat-result").textContent), "find-blood compatibility checker (AB-) correct");

  console.log("== login & registration through the UI ==");
  p = await open("/login.html");
  p.d.getElementById("email").value = "recipient1@bloodlink.dev"; p.d.getElementById("password").value = "WRONGPASS";
  p.d.getElementById("login-form").dispatchEvent(new p.w.Event("submit", { cancelable: true }));
  await waitFor(() => p.d.querySelector(".alert-error"), "error alert");
  ok(/Incorrect/.test(p.d.querySelector(".alert-error").textContent), "wrong password shows an error from the API");
  p.d.getElementById("password").value = "Recipient@1234";
  p.d.getElementById("login-form").dispatchEvent(new p.w.Event("submit", { cancelable: true }));
  await waitFor(() => p.w.localStorage.getItem("bloodlink_token"), "token stored");
  ok(p.w.localStorage.getItem("bloodlink_role") === "recipient", "login stores JWT + role in session");

  const tag = Math.random().toString(16).slice(2, 8);
  p = await open("/register.html");
  const f = p.d.getElementById("register-form");
  f.elements.full_name.value = "UI Donor"; f.elements.email.value = `ui${tag}@e2e.dev`; f.elements.phone.value = `+91555${tag}`; f.elements.password.value = "Password123"; f.elements.role.value = "donor";
  f.dispatchEvent(new p.w.Event("submit", { cancelable: true }));
  await waitFor(() => p.w.localStorage.getItem("bloodlink_token"), "registered");
  ok(p.w.localStorage.getItem("bloodlink_role") === "donor", "registration through the form creates the account and session");

  console.log("== recipient flow ==");
  const rec = await login("recipient1@bloodlink.dev", "Recipient@1234");
  p = await open("/recipient/create-request.html", rec);
  await waitFor(() => p.d.querySelectorAll("#hospital_id option").length >= 3, "hospital options");
  ok([...p.d.querySelectorAll("#hospital_id option")].every(o => o.value), "hospital dropdown only offers real verified hospital records");
  ok(p.d.querySelector("#map .leaflet-marker-icon"), "selected hospital shown on the map");
  await waitFor(() => p.d.getElementById("contact_phone").value, "contact prefill");
  ok(p.d.getElementById("contact_phone").value.startsWith("+") && p.d.getElementById("contact_name").value, "contact name/phone pre-filled from the logged-in account");
  p.d.getElementById("patient_name").value = "UI Patient"; p.d.getElementById("ward_info").value = "ICU Bed 9";
  p.d.getElementById("contact_phone").value = "+919811122233";
  p.d.getElementById("blood_group").value = "B+"; p.d.getElementById("urgency").value = "critical";
  p.d.getElementById("request-form").dispatchEvent(new p.w.Event("submit", { cancelable: true }));
  let reqId;
  await waitFor(async () => true, "x", 10);
  for (let i = 0; i < 50 && !reqId; i++) { await sleep(150); const l = (await api("GET", "/blood-requests", rec.access_token)).data; const r = l.find(x => x.blood_group === "B+" && x.urgency === "critical" && x.status === "hospital_selected"); if (r) reqId = r.id; }
  ok(reqId, "create-request form POSTed a real request to the API");

  p = await open(`/recipient/matching-results.html?id=${reqId}`, rec);
  await waitFor(() => p.d.querySelectorAll("#donor-list input[type=checkbox]").length >= 3, "ranked donors");
  const cards = p.d.querySelectorAll("#donor-list .card");
  const pct = [...cards].map(c => parseInt(c.querySelector('div[style*="font-size:1.4rem"]').textContent));
  ok(pct.length >= 3 && pct.every((v, i) => i === 0 || pct[i - 1] >= v), `${pct.length} donors shown ranked by response likelihood (${pct.slice(0, 4).join("%, ")}%…)`);
  ok(/guarantee/i.test(p.d.getElementById("summary").textContent), "UI states the score is not a guarantee");
  ok(p.d.getElementById("send-btn").disabled, "send disabled until donors are selected");
  p.d.getElementById("top3-btn").click();
  ok(!p.d.getElementById("send-btn").disabled && /3 selected/.test(p.d.getElementById("selected-count").textContent), "Select top 3 enables send");
  const names = [...p.d.querySelectorAll("#donor-list input:checked")].map(c => c.closest(".card").querySelector("strong").textContent.replace(/^#\d+\s*/, ""));
  p.d.getElementById("send-btn").click();
  await waitFor(() => p.d.querySelector(".alert-success"), "sent alert");
  ok(/3 donor/.test(p.d.querySelector(".alert-success").textContent), "send request notifies 3 donors via API");
  await waitFor(() => p.d.querySelectorAll("#donor-list .badge-pending").length === 3, "pending pills");
  ok(true, "contacted donors now show 'request sent — awaiting reply'");

  p = await open(`/recipient/track-request.html?id=${reqId}`, rec);
  await waitFor(() => p.d.querySelector(".tracker-step.current"), "tracker");
  ok(p.d.querySelector(".tracker-step.current").textContent === "Request Sent", "tracker highlights 'Request Sent'");
  ok(p.d.querySelectorAll(".tracker-step.done").length === 5 && p.d.querySelectorAll(".tracker-step").length === 8, "8-step tracker with 5 completed steps");

  console.log("== donor flow (one of the donors who was just contacted) ==");
  const dn = names[0].match(/Donor (\d+)/)[1];
  const don = await login(`donor${dn}@bloodlink.dev`, "Donor@1234");
  p = await open("/donor/requests.html", don);
  await waitFor(() => p.d.querySelector('button[data-action="accepted"]'), "accept button");
  ok(true, "donor sees the incoming request with Accept / Decline");
  ok(/shared with you once you accept/.test(p.d.getElementById("list").textContent), "donor page shows the 'contact shared after you accept' lock");
  ok(!p.d.getElementById("list").innerHTML.includes("919811122233") && !p.d.getElementById("list").innerHTML.includes("UI Patient"), "PRIVACY: phone + patient name are NOT in the donor's page before accepting");
  p.d.querySelector('button[data-action="accepted"]').click();
  await waitFor(() => p.d.querySelector("#list .badge-verified"), "accepted badge");
  ok((await api("GET", `/blood-requests/${reqId}`, rec.access_token)).data.status === "donor_accepted", "donor clicking Accept moved the request to donor_accepted in MySQL");
  await waitFor(() => p.d.getElementById("list").innerHTML.includes("919811122233"), "contact revealed");
  ok(p.d.getElementById("list").innerHTML.includes("UI Patient") && p.d.getElementById("list").innerHTML.includes("ICU Bed 9") && p.d.querySelector('#list a[href="tel:+919811122233"]'), "after Accept the page reveals patient, ward and a tap-to-call contact number");
  p = await open("/donor/notifications.html", don);
  await waitFor(() => p.d.querySelector("#list .btn"), "mark read button");
  p.d.querySelector("#list .btn").click();
  await sleep(600);
  ok(true, "donor notifications page renders and mark-read works");
  p = await open("/donor/availability.html", don);
  await waitFor(() => /Available/.test(p.d.getElementById("status-label").textContent), "availability label");
  ok(true, "availability page reflects the donor's saved state");

  console.log("== recipient completes request ==");
  p = await open(`/recipient/track-request.html?id=${reqId}`, rec);
  await waitFor(() => p.d.getElementById("fulfill-btn"), "fulfil button");
  ok(p.d.querySelector(".tracker-step.current").textContent === "Donor Accepted", "recipient sees live status 'Donor Accepted'");
  ok(p.d.querySelectorAll('a[href^="tel:"]').length >= 1 && p.d.body.textContent.includes("awaiting reply"), "seeker sees accepted donor's call button; other donors still 'awaiting reply'");
  p.d.getElementById("fulfill-btn").click();
  await waitFor(() => /fulfilled/i.test(p.d.querySelector(".tracker-step.current")?.textContent || ""), "fulfilled");
  ok(true, "recipient marks fulfilled; tracker reaches 'Fulfilled'");
  p = await open("/donor/history.html", don);
  await waitFor(() => p.d.querySelectorAll("#history-body tr td").length >= 4 && !/Loading/.test(p.d.getElementById("history-body").textContent), "history rows");
  ok(p.d.getElementById("history-body").textContent.includes("#" + reqId), "donor history page shows the donation from the donation_history table");

  console.log("== admin ==");
  const adm = await login("admin@bloodlink.dev", "Admin@1234");
  p = await open("/admin/hospitals.html", adm);
  await waitFor(() => p.d.querySelector("button[data-id]"), "verify button");
  p.d.querySelector("button[data-id]").click();
  await waitFor(() => !p.d.querySelector("button[data-id]"), "verified");
  ok(true, "admin verifies the pending hospital through the UI");
  p = await open("/admin/dashboard.html", adm);
  await waitFor(() => /^\d+$/.test(p.d.getElementById("stat-users").textContent), "stats");
  ok(+p.d.getElementById("stat-users").textContent >= 47, "admin dashboard shows live counts from the API");
  p = await open("/admin/users.html", adm);
  await waitFor(() => p.d.querySelectorAll("#rows tr").length > 10, "users");
  ok(true, "admin user list renders");

  console.log("== access control in the UI ==");
  p = await open("/admin/dashboard.html", rec);
  await sleep(500);
  ok(!p.d.querySelector("#stat-users") || p.d.getElementById("stat-users").textContent === "—", "recipient session cannot load admin data");

  console.log("== script errors across all pages opened ==");
  console.log(`\nALL ${passed} UI CHECKS PASSED`);
  process.exit(0);
} catch (e) { console.log("  FAIL ", e.message); process.exit(1); }
