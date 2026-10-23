// services/donor.js - POST/GET/PUT /donors, /donors/me, /donors/availability
const DonorService = {
  create(payload) {
    return BloodLinkAPI.apiRequest("/donors", { method: "POST", body: payload });
  },
  getMe() {
    return BloodLinkAPI.apiRequest("/donors/me", { method: "GET" });
  },
  updateMe(payload) {
    return BloodLinkAPI.apiRequest("/donors/me", { method: "PUT", body: payload });
  },
  getAvailability() {
    return BloodLinkAPI.apiRequest("/donors/availability", { method: "GET" });
  },
  getHistory() {
    return BloodLinkAPI.apiRequest("/donors/me/history", { method: "GET" });
  },
  setAvailability(is_available) {
    return BloodLinkAPI.apiRequest("/donors/availability", { method: "PUT", body: { is_available } });
  },
};
window.DonorService = DonorService;
