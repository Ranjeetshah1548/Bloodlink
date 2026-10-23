// Shared by donor/notifications.html and recipient/notifications.html.
// Requires app.js + notification.js to already be loaded, and expects
// #alert-box and #list containers to exist on the page.
(function () {
  const alertBox = document.getElementById("alert-box");
  const listEl = document.getElementById("list");

  function typeIcon(type) {
    return { match_request: "🩸", donor_accept: "✅", donor_decline: "↩️", request_update: "📋" }[type] || "🔔";
  }

  async function load() {
    clearAlert(alertBox);
    listEl.innerHTML = `<div class="skeleton" style="height:60px;"></div>`;
    try {
      const notes = await NotificationService.list();
      listEl.innerHTML = notes.length ? "" : `<div class="empty-state">No notifications yet.</div>`;
      notes.forEach(n => {
        const row = document.createElement("div");
        row.style.cssText = "padding:14px 0; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; gap:12px; align-items:flex-start;";
        row.innerHTML = `
          <div>
            <div style="font-weight:${n.is_read ? 500 : 700};">${typeIcon(n.type)} ${escapeHtml(n.title)}</div>
            <div class="muted" style="font-size:0.88rem; margin-top:2px;">${escapeHtml(n.message)}</div>
            <div class="muted" style="font-size:0.76rem; margin-top:4px;">${fmtDateTime(n.created_at)}</div>
          </div>
          ${n.is_read ? "" : `<button class="btn btn-ghost btn-sm" data-id="${n.id}">Mark read</button>`}
        `;
        listEl.appendChild(row);
      });
      listEl.querySelectorAll("button[data-id]").forEach(btn => {
        btn.addEventListener("click", async () => {
          try { await NotificationService.markRead(btn.dataset.id); load(); }
          catch (e) { showAlert(alertBox, e.message); }
        });
      });
    } catch (e) {
      showAlert(alertBox, e.message);
      listEl.innerHTML = "";
    }
  }
  load();
})();
