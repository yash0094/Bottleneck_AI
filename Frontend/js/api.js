// api.js — thin fetch wrapper shared by every page.

const Api = {
  token() {
    return localStorage.getItem("flowlens_token") || "";
  },

  setSession(token, user) {
    localStorage.setItem("flowlens_token", token);
    localStorage.setItem("flowlens_user", JSON.stringify(user));
  },

  clearSession() {
    localStorage.removeItem("flowlens_token");
    localStorage.removeItem("flowlens_user");
  },

  currentUser() {
    try {
      return JSON.parse(localStorage.getItem("flowlens_user") || "null");
    } catch {
      return null;
    }
  },

  requireAuth() {
    if (!this.token()) {
      window.location.href = "index.html";
    }
  },

  async request(path, { method = "GET", body, isForm = false } = {}) {
    const headers = {};
    if (this.token()) headers["Authorization"] = `Bearer ${this.token()}`;
    if (!isForm && body) headers["Content-Type"] = "application/json";

    const res = await fetch(`${window.API_BASE_URL}${path}`, {
      method,
      headers,
      body: isForm ? body : body ? JSON.stringify(body) : undefined,
    });

    if (res.status === 401) {
      this.clearSession();
      window.location.href = "index.html";
      return;
    }

    const contentType = res.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      return res; // e.g. PDF download — caller handles the blob
    }

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Something went wrong.");
    return data;
  },

  get(path) {
    return this.request(path);
  },
  post(path, body) {
    return this.request(path, { method: "POST", body });
  },
  patch(path, body) {
    return this.request(path, { method: "PATCH", body });
  },
  del(path) {
    return this.request(path, { method: "DELETE" });
  },
  postForm(path, formData) {
    return this.request(path, { method: "POST", body: formData, isForm: true });
  },
};

function showError(el, message) {
  if (!el) return;
  el.textContent = message;
  el.style.display = message ? "block" : "none";
}

function fmtSeconds(s) {
  if (s === null || s === undefined || isNaN(s)) return "-";
  const totalMin = s / 60;
  if (totalMin < 60) return `${totalMin.toFixed(1)} min`;
  const hrs = totalMin / 60;
  if (hrs < 24) return `${hrs.toFixed(1)} hrs`;
  return `${(hrs / 24).toFixed(1)} days`;
}
