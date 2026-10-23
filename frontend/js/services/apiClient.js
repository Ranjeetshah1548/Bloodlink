// Thin fetch wrapper shared by every service module. Talks to the REAL
// FastAPI backend - no mock data, no localStorage-as-database. localStorage
// is used ONLY to hold the JWT + a small cached copy of "who am I", exactly
// like any real single-page app would.
const API_BASE = window.BLOODLINK_CONFIG.API_BASE_URL;

function getToken() {
  return localStorage.getItem("bloodlink_token");
}

function setSession({ access_token, role, user_id, full_name }) {
  localStorage.setItem("bloodlink_token", access_token);
  localStorage.setItem("bloodlink_role", role);
  localStorage.setItem("bloodlink_user_id", String(user_id));
  localStorage.setItem("bloodlink_full_name", full_name);
}

function clearSession() {
  localStorage.removeItem("bloodlink_token");
  localStorage.removeItem("bloodlink_role");
  localStorage.removeItem("bloodlink_user_id");
  localStorage.removeItem("bloodlink_full_name");
}

function getSession() {
  const token = getToken();
  if (!token) return null;
  return {
    token,
    role: localStorage.getItem("bloodlink_role"),
    userId: localStorage.getItem("bloodlink_user_id"),
    fullName: localStorage.getItem("bloodlink_full_name"),
  };
}

async function apiRequest(path, { method = "GET", body, auth = true, params } = {}) {
  let url = `${API_BASE}${path}`;
  if (params) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
    ).toString();
    if (qs) url += `?${qs}`;
  }

  const headers = { "Content-Type": "application/json" };
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (networkErr) {
    throw new ApiError(
      0,
      `Could not reach the BloodLink API at ${API_BASE}. Is the backend running?`
    );
  }

  if (response.status === 204) return null;

  let data = null;
  const text = await response.text();
  if (text) {
    try { data = JSON.parse(text); } catch { data = text; }
  }

  if (!response.ok) {
    const detail = (data && (data.detail || data.message)) || response.statusText;
    if (response.status === 401 && auth) {
      // token invalid/expired/revoked -> force re-login
      clearSession();
    }
    throw new ApiError(response.status, Array.isArray(detail) ? detail.map(d => d.msg).join("; ") : detail);
  }

  return data;
}

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

window.BloodLinkAPI = { apiRequest, ApiError, getToken, setSession, clearSession, getSession };
