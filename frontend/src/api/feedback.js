import { api } from "./client";

export const feedbackApi = {
  myForms: () => api.get("/forms/my").then((r) => r.data),
  form: (id) => api.get(`/forms/${id}`).then((r) => r.data),
  submit: (id, body) => api.post(`/forms/${id}/responses`, body).then((r) => r.data),
  cycles: () => api.get("/cycles").then((r) => r.data),
  cycle: (id) => api.get(`/cycles/${id}`).then((r) => r.data),
  createCycle: (body) => api.post("/cycles", body).then((r) => r.data),
  preview: (id) => api.get(`/cycles/${id}/preview`).then((r) => r.data),
  publish: (id) => api.post(`/cycles/${id}/publish`).then((r) => r.data),
  close: (id) => api.post(`/cycles/${id}/close`).then((r) => r.data),
  cycleForms: (id) => api.get(`/cycles/${id}/forms`).then((r) => r.data),
  facultyFeedback: (facultyId, params) =>
    api.get(`/feedback/faculty/${facultyId}`, { params }).then((r) => r.data),
};

export const LIKERT_LABELS = { 1: "Poor", 2: "Fair", 3: "Good", 4: "Very good", 5: "Excellent" };

export function formatDate(value, withTime = false) {
  if (!value) return "";
  return new Date(value).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "numeric", minute: "2-digit" } : {}),
  });
}
