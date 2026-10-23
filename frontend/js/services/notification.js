// services/notification.js - GET /notifications, PUT /notifications/{id}/read
const NotificationService = {
  list(unreadOnly = false) {
    return BloodLinkAPI.apiRequest("/notifications", { method: "GET", params: { unread_only: unreadOnly } });
  },
  markRead(id) {
    return BloodLinkAPI.apiRequest(`/notifications/${id}/read`, { method: "PUT" });
  },
};
window.NotificationService = NotificationService;

// services/report.js (small enough to co-locate) - POST /reports
const ReportService = {
  create(payload) {
    return BloodLinkAPI.apiRequest("/reports", { method: "POST", body: payload });
  },
  mine() {
    return BloodLinkAPI.apiRequest("/reports/my", { method: "GET" });
  },
};
window.ReportService = ReportService;
