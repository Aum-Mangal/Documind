// Centralized API client for DocuMind

const getBaseUrl = () => {
  const envUrl = typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_API_URL ? import.meta.env.VITE_API_URL : "";
  const stored = localStorage.getItem("DOCUMIND_API_URL");
  return (stored || envUrl || "").replace(/\/$/, "");
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

const request = async (endpoint, options = {}) => {
  const baseUrl = getBaseUrl();
  const url = `${baseUrl}${endpoint}`;

  const headers = {
    ...(options.headers || {}),
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

  if (!response.ok) {
    throw new Error(data.detail || data.message || `Request failed (${response.status})`);
  }

  return data;
};

export const api = {
  // Auth
  async signup(email, password) {
    return request("/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  },

  async login(email, password) {
    const res = await request("/auth/login", {
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
    const token = getToken();
    return request(`/docs/documents?token=${token}`);
  },

  async uploadDocument(file) {
    const token = getToken();
    const formData = new FormData();
    formData.append("file", file);

    return request(`/docs/upload?token=${token}`, {
      method: "POST",
      body: formData,
    });
  },

  async getEntities(docId) {
    const token = getToken();
    return request(`/docs/documents/${docId}/entities?token=${token}`);
  },

  async getDocumentGraph(docId) {
    const token = getToken();
    return request(`/docs/documents/${docId}/graph?token=${token}`);
  },

  async getGlobalGraph() {
    const token = getToken();
    return request(`/docs/graph/global?token=${token}`);
  },

  async chatWithDocument(docId, question) {
    const token = getToken();
    return request(`/docs/documents/${docId}/chat?token=${token}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  },
};
