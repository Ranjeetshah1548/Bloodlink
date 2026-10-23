// services/bloodRequest.js - /blood-requests CRUD
const BloodRequestService = {
  create(payload) {
    return BloodLinkAPI.apiRequest("/blood-requests", { method: "POST", body: payload });
  },
  list() {
    return BloodLinkAPI.apiRequest("/blood-requests", { method: "GET" });
  },
  get(requestId) {
    return BloodLinkAPI.apiRequest(`/blood-requests/${requestId}`, { method: "GET" });
  },
  responders(requestId) {
    return BloodLinkAPI.apiRequest(`/blood-requests/${requestId}/responders`, { method: "GET" });
  },
  update(requestId, payload) {
    return BloodLinkAPI.apiRequest(`/blood-requests/${requestId}`, { method: "PUT", body: payload });
  },
};
window.BloodRequestService = BloodRequestService;
