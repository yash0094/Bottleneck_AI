// Point this at your deployed backend (Render Web Service) URL.
// Example: "https://flowlens-api.onrender.com"
// Leave as-is for local dev if you run the backend on localhost:8000.
window.API_BASE_URL =
  window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://localhost:8000"
    : "https://YOUR-BACKEND-URL.onrender.com";
