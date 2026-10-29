// Centralized API client for DocuMind

// Fired when the server rejects the stored token (expired or invalid)
export const UNAUTHORIZED_EVENT = "documind:unauthorized";

const getBaseUrl = () => {
  // Only set at build time; never read from localStorage, where it could be tampered with
  const envUrl = import.meta.env.VITE_API_URL || "";
  return envUrl.replace(/\/$/, "");
};

const getToken = () => {
  return localStorage.getItem("documind_token");
};

export const setToken = (token) => {
  if (token) {
    localStorage.setItem("documind_token", token);
  } else {
    localStorage.removeItem("documind_token");
  }
};

export const isAuthenticated = () => {
  return !!getToken();
};

const errorMessage = (data, status) => {
  // FastAPI validation errors (422) return a list of { msg, loc } objects
  if (Array.isArray(data.detail)) {
    return data.detail.map((d) => d.msg).join("; ");
  }
  return data.detail || data.message || `Request failed (${status})`;
};

const request = async (endpoint, { auth = true, ...options } = {}) => {
  const url = `${getBaseUrl()}${endpoint}`;
  const token = auth ? getToken() : null;

  const headers = {
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  let data;
  try {
    data = await response.json();
  } catch (_) {
    data = { detail: `Server error (${response.status}): ${response.statusText || 'Unknown response'}` };
  }

  if (response.status === 401 && token) {
    setToken(null);
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  }

  if (!response.ok) {
    throw new Error(errorMessage(data, response.status));
  }

  return data;
};

export const api = {
  // Auth
  async signup(email, password) {
    return request("/auth/signup", {
      auth: false,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  },

  async login(email, password) {
    const res = await request("/auth/login", {
      auth: false,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (res.access_token) {
      setToken(res.access_token);
    }
    return res;
  },

  logout() {
    setToken(null);
  },

  // Documents
  async listDocuments() {
    return request("/docs/documents");
  },

  async uploadDocument(file) {
    const formData = new FormData();
    formData.append("file", file);

    return request("/docs/upload", {
      method: "POST",
      body: formData,
    });
  },

  async getEntities(docId) {
    return request(`/docs/documents/${docId}/entities`);
  },

  async getDocumentGraph(docId) {
    return request(`/docs/documents/${docId}/graph`);
  },

  async getGlobalGraph() {
    return request("/docs/graph/global");
  },

  async chatWithDocument(docId, question) {
    return request(`/docs/documents/${docId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  },
};
