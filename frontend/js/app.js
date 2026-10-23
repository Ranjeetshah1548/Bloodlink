// app.js - shared across every page. Renders the header/footer based on
// real session state (JWT in localStorage), and provides small DOM helpers
// used by page-level scripts.

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function fmtDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function urgencyBadgeClass(u) {
  return { low: "badge-neutral", medium: "badge-info", high: "badge-pending", critical: "badge-critical" }[u] || "badge-neutral";
}

function renderHeader() {
  const mount = document.getElementById("site-header");
  if (!mount) return;
  const session = window.AuthService ? AuthService.currentSession() : null;

  let dashboardLink = "";
  let rightSide = "";
  if (session) {
    const dashByRole = { donor: "/donor/dashboard.html", recipient: "/recipient/dashboard.html", admin: "/admin/dashboard.html" };
    dashboardLink = dashByRole[session.role] || "/index.html";
    rightSide = `
      <span class="muted" style="font-size:0.85rem;">Hi, ${escapeHtml(session.fullName)}</span>
      <a class="btn btn-outline btn-sm" href="${dashboardLink}">Dashboard</a>
      <button class="btn btn-ghost btn-sm" id="logout-btn" type="button">Log out</button>
    `;
  } else {
    rightSide = `
      <a class="btn btn-ghost btn-sm" href="/login.html">Log in</a>
      <a class="btn btn-accent btn-sm" href="/register.html">Register</a>
    `;
  }

  mount.innerHTML = `
    <div class="nav">
      <a href="/index.html" class="brand"><span class="drop"></span> BloodLink</a>
      <ul class="nav-links">
        <li><a href="/index.html">Home</a></li>
        <li><a href="/find-blood.html">Find Blood</a></li>
        <li><a href="/hospitals.html">Hospitals</a></li>
        <li><a href="/how-it-works.html">How It Works</a></li>
        <li><a href="/about.html">About</a></li>
      </ul>
      <div class="nav-actions">${rightSide}</div>
    </div>
  `;

  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
      await AuthService.logout();
      window.location.href = "/index.html";
    });
  }
}

function renderFooter() {
  const mount = document.getElementById("site-footer");
  if (!mount) return;
  mount.innerHTML = `
    <div class="container flex-between" style="flex-wrap:wrap; gap:16px;">
      <div>© ${new Date().getFullYear()} BloodLink. Connecting verified hospitals with willing donors.</div>
      <div class="flex gap-16">
        <a href="/about.html">About</a>
        <a href="/how-it-works.html">How It Works</a>
        <a href="/hospitals.html">Hospitals</a>
      </div>
    </div>
  `;
}

function renderDashSidebar(activeHref, items) {
  const mount = document.getElementById("dash-sidebar");
  if (!mount) return;
  mount.innerHTML = items.map(([href, label]) =>
    `<a href="${href}" class="${href === activeHref ? "active" : ""}">${label}</a>`
  ).join("");
}

function showAlert(container, message, type = "error") {
  container.innerHTML = `<div class="alert alert-${type}">${escapeHtml(message)}</div>`;
}

function clearAlert(container) {
  container.innerHTML = "";
}

document.addEventListener("DOMContentLoaded", () => {
  renderHeader();
  renderFooter();
});
