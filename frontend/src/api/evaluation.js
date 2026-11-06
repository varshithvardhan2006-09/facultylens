import { api } from "./client";

export const labelsApi = {
  next: () => api.get("/labels/next").then((r) => r.data),
  save: (body) => api.post("/labels", body).then((r) => r.data),
  progress: () => api.get("/labels/progress").then((r) => r.data),
  disagreements: () => api.get("/labels/disagreements").then((r) => r.data),
  resolve: (body) => api.post("/labels/resolve", body).then((r) => r.data),
  nextGroup: () => api.get("/labels/groups/next").then((r) => r.data),
  saveReference: (id, body) => api.post(`/labels/groups/${id}/reference`, body).then((r) => r.data),
  nextGrounding: () => api.get("/labels/grounding/next").then((r) => r.data),
  saveGrounding: (body) => api.post("/labels/grounding", body).then((r) => r.data),
};

export const evaluationApi = {
  results: () => api.get("/evaluation/results").then((r) => r.data),
};

export const surveyApi = {
  mine: () => api.get("/survey/mine").then((r) => r.data),
  save: (body) => api.post("/survey", body).then((r) => r.data),
};

/** The eight teaching aspects, in the questionnaire's order (SPEC §4). */
export const ASPECTS = [
  ["knowledge", "Subject knowledge"],
  ["clarity", "Clarity of explanation"],
  ["punctuality", "Punctuality & regularity"],
  ["interaction", "Interaction & doubt clearing"],
  ["practical", "Examples & practical relevance"],
  ["assessment", "Assessment & feedback fairness"],
  ["behaviour", "Behaviour & approachability"],
  ["pace", "Pace & syllabus coverage"],
];
