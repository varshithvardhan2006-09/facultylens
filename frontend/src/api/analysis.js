import { api } from "./client";

export const analysisApi = {
  summary: (cycle) => api.get("/analysis/summary", { params: { cycle } }).then((r) => r.data),
  run: (cycle) => api.post("/analysis/run", null, { params: { cycle } }).then((r) => r.data),
  status: (job) => api.get(`/analysis/status/${job}`).then((r) => r.data),
  jobs: (limit = 20) => api.get("/analysis/jobs", { params: { limit } }).then((r) => r.data),
  summaries: (cycle) =>
    api.post("/analysis/summaries", null, { params: { cycle } }).then((r) => r.data),
  queue: (params) => api.get("/moderation/queue", { params }).then((r) => r.data),
  // A decision also rewrites the course summary, which can wait on the LLM.
  decide: (id, body) =>
    api.post(`/moderation/${id}/decision`, body, { timeout: 90000 }).then((r) => r.data),
};

/** Fired after a moderation decision so the nav count refreshes without a reload. */
export const MODERATION_CHANGED = "facultylens:moderation-changed";

export const FIELD_LABELS = {
  liked: "Liked most",
  improve: "Should improve",
  other: "Other comments",
  comment: "Syllabus comment",
};

export function formatSeconds(s) {
  if (s == null) return "–";
  if (s < 60) return `${s.toFixed(s < 10 ? 1 : 0)} s`;
  const m = Math.floor(s / 60);
  return `${m} min ${String(Math.round(s % 60)).padStart(2, "0")} s`;
}
