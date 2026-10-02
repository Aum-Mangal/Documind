// DocuMind Backend API Configuration
// Once you deploy your backend to Hugging Face Spaces, replace this URL with your Space URL:
// Example: "https://<your-username>-<your-space-name>.hf.space"
// For local backend testing, use: "http://127.0.0.1:8000"

const DEFAULT_API_URL = "https://web-production-d2b44.up.railway.app";

const API = localStorage.getItem("DOCUMIND_API_URL") || DEFAULT_API_URL;
