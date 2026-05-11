import axios from "axios";
import config from "../config";

// Public — no auth (GET /health)
const API = axios.create({
  baseURL: config.apiBaseUrl,
});

// Authenticated — Basic Auth for all protected endpoints
const AuthAPI = axios.create({
  baseURL: config.apiBaseUrl,
  auth: {
    username: import.meta.env.VITE_API_USERNAME || "",
    password: import.meta.env.VITE_API_PASSWORD || "",
  },
});

// ── Public ────────────────────────────────────────────────────────────────────
export const getHealth           = ()          => API.get("/health");

// ── Protected ─────────────────────────────────────────────────────────────────
export const postScoreBehaviour  = (body)      => AuthAPI.post("/score-behaviour", body);
export const postBulkSimulate    = (body)      => AuthAPI.post("/simulate/bulk", body);
export const postResetSimulate   = ()          => AuthAPI.post("/simulate/reset", { confirm: true });
export const postMetricsSummary  = (accountId) => AuthAPI.post("/metrics/summary", { account_id: accountId });
export const postProfileRetrieve = (accountId) => AuthAPI.post("/profile/retrieve", { account_id: accountId });
export const postTxnHistory      = (accountId) => AuthAPI.post("/transactions/history", { account_id: accountId });
export const postScoringResults  = (accountId) => AuthAPI.post("/scoring-results", { account_id: accountId });
export const postConfigRetrieve  = (body)      => AuthAPI.post("/config/rules/retrieve", body);
export const postConfigUpdate    = (rules)     => AuthAPI.post("/config/rules/update", { rules });

export default API;
