// map.js - OpenStreetMap (Leaflet) hospital map. Needs Leaflet loaded first
// (see the <link>/<script> tags for unpkg.com/leaflet in the page <head>).
// No API key required. To use Google Maps instead, swap this module's
// implementation; pages only call BloodLinkMap.render / .highlight.
const BloodLinkMap = (() => {
  let map, layer, markers = {};

  function render(containerId, hospitals, { onSelect, selectedId, height = 360 } = {}) {
    const el = document.getElementById(containerId);
    el.style.height = height + "px";
    el.style.borderRadius = "12px";
    el.style.border = "1px solid var(--border)";
    if (!window.L) {
      el.innerHTML = '<div class="empty-state">Map library failed to load (check your internet connection).</div>';
      return;
    }
    if (map) { map.remove(); map = null; }
    markers = {};
    map = L.map(containerId, { scrollWheelZoom: false });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
    layer = L.layerGroup().addTo(map);

    const pts = [];
    hospitals.forEach(h => {
      const m = L.marker([h.latitude, h.longitude]).addTo(layer);
      const dist = h.distance_km != null ? `<br>📏 ${h.distance_km} km from you` : "";
      m.bindPopup(`<strong>${escapeHtml(h.name)}</strong><br>${escapeHtml(h.address)}, ${escapeHtml(h.city)}
        <br><span style="color:#1F8A5F;font-weight:600;">${h.is_verified ? "✓ Verified" : "Pending verification"}</span>${dist}`);
      if (onSelect) m.on("click", () => onSelect(h));
      markers[h.id] = m;
      pts.push([h.latitude, h.longitude]);
    });
    if (pts.length === 1) map.setView(pts[0], 14);
    else if (pts.length) map.fitBounds(pts, { padding: [30, 30] });
    else map.setView([22.5, 79], 4);
    if (selectedId) highlight(selectedId);
    return map;
  }

  function highlight(id) {
    const m = markers[id];
    if (!m || !map) return;
    map.setView(m.getLatLng(), Math.max(map.getZoom(), 13));
    m.openPopup();
  }

  function userLocation() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) return reject(new Error("Geolocation is not supported by this browser."));
      navigator.geolocation.getCurrentPosition(
        p => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
        () => reject(new Error("Could not read your location. Allow location access or filter by city.")),
        { timeout: 8000 });
    });
  }

  return { render, highlight, userLocation };
})();
window.BloodLinkMap = BloodLinkMap;
