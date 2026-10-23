// services/auth.js - talks to POST /auth/register, /auth/login, /auth/verify-otp, /auth/logout
const AuthService = {
  async register({ full_name, email, phone, password, role }) {
    const data = await BloodLinkAPI.apiRequest("/auth/register", {
      method: "POST", auth: false,
      body: { full_name, email, phone, password, role },
    });
    BloodLinkAPI.setSession(data);
    return data;
  },

  async login({ email, password }) {
    const data = await BloodLinkAPI.apiRequest("/auth/login", {
      method: "POST", auth: false,
      body: { email, password },
    });
    BloodLinkAPI.setSession(data);
    return data;
  },

  async verifyOtp({ phone, code }) {
    return BloodLinkAPI.apiRequest("/auth/verify-otp", {
      method: "POST", auth: false,
      body: { phone, code },
    });
  },

  async logout() {
    try {
      await BloodLinkAPI.apiRequest("/auth/logout", { method: "POST" });
    } finally {
      BloodLinkAPI.clearSession();
    }
  },

  me() {
    return BloodLinkAPI.apiRequest("/auth/me", { method: "GET" });
  },

  currentSession() {
    return BloodLinkAPI.getSession();
  },

  requireRole(roles, redirectTo = "/login.html") {
    const session = BloodLinkAPI.getSession();
    if (!session || !roles.includes(session.role)) {
      window.location.href = redirectTo;
      return null;
    }
    return session;
  },
};

window.AuthService = AuthService;
