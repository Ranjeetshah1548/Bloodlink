// services/hospital.js - GET /hospitals, /hospitals/{id}
const HospitalService = {
  list({ city, verified_only = true, lat, lng } = {}) {
    return BloodLinkAPI.apiRequest("/hospitals", {
      method: "GET",
      params: { city, verified_only, lat, lng },
    });
  },
  get(hospitalId) {
    return BloodLinkAPI.apiRequest(`/hospitals/${hospitalId}`, { method: "GET" });
  },
};
window.HospitalService = HospitalService;
