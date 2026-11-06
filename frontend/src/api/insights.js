import { api } from "./client";

const clean = (params) => Object.fromEntries(Object.entries(params).filter(([, v]) => v));

export const insightsApi = {
  department: (id, cycle) =>
    api.get(`/analytics/department/${id}`, { params: clean({ cycle }) }).then((r) => r.data),
  bias: (department, cycle) =>
    api.get("/analytics/bias", { params: clean({ department, cycle }) }).then((r) => r.data),
  sarcasm: (department, cycle) =>
    api.get("/analytics/sarcasm", { params: clean({ department, cycle }) }).then((r) => r.data),
  faculty: (id, cycle) =>
    api.get(`/analytics/faculty/${id}`, { params: clean({ cycle }) }).then((r) => r.data),
};

export const pct = (v) => (v == null ? "–" : `${Math.round(v * 100)}%`);
export const signed = (v) => (v == null ? "–" : v > 0 ? `+${v.toFixed(2)}` : v.toFixed(2));
