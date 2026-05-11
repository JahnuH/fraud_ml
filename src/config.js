// ─── API CONFIGURATION ───────────────────────────────────────────────────────
//
// DEV  (npm run dev):
//   All requests go to /api/*
//   Vite proxy rewrites /api/* → https://aml.innovitegra.in/frms/behaviour/*
//   No CORS needed — proxy runs server-side
//
// PROD (npm run build):
//   VITE_API_BASE_URL must be set in .env.production
//   Requires CORS to be enabled on the backend for the deployed frontend origin
//   Backend team must allow: allow_origins=["https://your-frontend-domain.com"]
//
// Backend base: https://aml.innovitegra.in/frms/behaviour
// Endpoints:
//   GET  /health          → health check
//   POST /score-behavior  → behavioral anomaly detection

const config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || "/api",
};

export default config;
