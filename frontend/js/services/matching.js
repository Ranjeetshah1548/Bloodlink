// services/matching.js - POST /match-donors/{request_id}, /donor-responses
const MatchingService = {
  runMatch(requestId) {
    return BloodLinkAPI.apiRequest(`/match-donors/${requestId}`, { method: "POST" });
  },
  sendRequests(requestId, donorIds) {
    return BloodLinkAPI.apiRequest(`/match-donors/${requestId}/send`, {
      method: "POST", body: { donor_ids: donorIds },
    });
  },
};

const DonorResponseService = {
  answer({ request_id, donor_id, response }) {
    return BloodLinkAPI.apiRequest("/donor-responses", {
      method: "POST",
      body: { request_id, donor_id, response },
    });
  },
  my() {
    return BloodLinkAPI.apiRequest("/donor-responses/my", { method: "GET" });
  },
};

window.MatchingService = MatchingService;
window.DonorResponseService = DonorResponseService;
