// services/admin.js - /admin/* endpoints
const AdminService = {
  listUsers() {
    return BloodLinkAPI.apiRequest("/admin/users", { method: "GET" });
  },
  setUserActive(userId, is_active) {
    return BloodLinkAPI.apiRequest(`/admin/users/${userId}/active`, { method: "PUT", body: { is_active } });
  },
  listDonors() {
    return BloodLinkAPI.apiRequest("/admin/donors", { method: "GET" });
  },
  listHospitals() {
    return BloodLinkAPI.apiRequest("/admin/hospitals", { method: "GET" });
  },
  verifyHospital(hospitalId) {
    return BloodLinkAPI.apiRequest(`/admin/hospitals/${hospitalId}/verify`, { method: "PUT" });
  },
  createHospital(payload) {
    return BloodLinkAPI.apiRequest("/hospitals", { method: "POST", body: payload });
  },
  listReports() {
    return BloodLinkAPI.apiRequest("/admin/reports", { method: "GET" });
  },
  updateReport(reportId, status) {
    return BloodLinkAPI.apiRequest(`/admin/reports/${reportId}`, { method: "PUT", body: { status } });
  },
};
window.AdminService = AdminService;
