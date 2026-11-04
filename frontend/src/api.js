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

const authHeaders = (auth = true) => {
  const token = auth ? getToken() : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const handleUnauthorized = (response, sentToken) => {
  if (response.status === 401 && sentToken) {
    setToken(null);
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  }
};

const errorMessage = (data, status) => {
  // FastAPI validation errors (422) return a list of { msg, loc } objects
  if (Array.isArray(data.detail)) {
    return data.detail.map((d) => d.msg).join("; ");
  }
  return data.detail || data.message || `Request failed (${status})`;
};

const request = async (endpoint, { auth = true, ...options } = {}) => {
  const headers = { ...(options.headers || {}), ...authHeaders(auth) };
  const response = await fetch(`${getBaseUrl()}${endpoint}`, { ...options, headers });
  handleUnauthorized(response, !!headers.Authorization);

  if (response.status === 204) return null;

  let data;
  try {
    data = await response.json();
  } catch {
    data = { detail: `Server error (${response.status}): ${response.statusText || 'Unknown response'}` };
  }

  if (!response.ok) {
    const error = new Error(errorMessage(data, response.status));
    error.status = response.status;
    throw error;
  }
  return data;
};

const json = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  // Auth
  async signup(email, password) {
    return request("/api/auth/signup", { auth: false, ...json("POST", { email, password }) });
  },

  async login(email, password) {
    const res = await request("/api/auth/login", { auth: false, ...json("POST", { email, password }) });
    if (res.access_token) {
      setToken(res.access_token);
    }
    return res;
  },

  logout() {
    setToken(null);
  },

  // Documents
  listDocuments() {
    return request("/api/documents");
  },

  getDocument(docId) {
    return request(`/api/documents/${docId}`);
  },

  // Resolves to { document, duplicate }; processing continues in the background
  uploadDocument(file) {
    const formData = new FormData();
    formData.append("file", file);
    return request("/api/documents", { method: "POST", body: formData });
  },

  deleteDocument(docId) {
    return request(`/api/documents/${docId}`, { method: "DELETE" });
  },

  reprocessDocument(docId) {
    return request(`/api/documents/${docId}/reprocess`, { method: "POST" });
  },

  async downloadDocument(doc) {
    const headers = authHeaders();
    const response = await fetch(`${getBaseUrl()}/api/documents/${doc.id}/file`, { headers });
    handleUnauthorized(response, !!headers.Authorization);
    if (!response.ok) throw new Error("Could not download the original file.");
    const url = URL.createObjectURL(await response.blob());
    const link = Object.assign(document.createElement("a"), { href: url, download: doc.filename });
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },

  // Streams processing progress (server-sent events) until the document is ready, failed
  // or deleted. fetch is used instead of EventSource so the token can go in a header.
  async watchDocument(docId, onState, signal) {
    const headers = authHeaders();
    const response = await fetch(`${getBaseUrl()}/api/documents/${docId}/events`, { headers, signal });
    handleUnauthorized(response, !!headers.Authorization);
    if (!response.ok || !response.body) throw new Error(`Progress stream failed (${response.status})`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) return;
      buffer += decoder.decode(value, { stream: true });
      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const event = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = event.split("\n").filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trim()).join("");
        if (data) onState(JSON.parse(data));
      }
    }
  },

  getEntities(docId) {
    return request(`/api/documents/${docId}/entities`);
  },

  getDocumentGraph(docId) {
    return request(`/api/documents/${docId}/graph`);
  },

  getGlobalGraph() {
    return request("/api/graph");
  },

  // Chat. Without conversationId a new conversation starts, searching documentIds
  // (or every document when omitted). Resolves to { conversation, message, search_query }.
  ask({ question, conversationId, documentIds }) {
    return request("/api/chat", json("POST", {
      question,
      conversation_id: conversationId ?? null,
      document_ids: documentIds?.length ? documentIds : null,
    }));
  },

  listConversations() {
    return request("/api/conversations");
  },

  getConversation(conversationId) {
    return request(`/api/conversations/${conversationId}`);
  },

  deleteConversation(conversationId) {
    return request(`/api/conversations/${conversationId}`, { method: "DELETE" });
  },
};
