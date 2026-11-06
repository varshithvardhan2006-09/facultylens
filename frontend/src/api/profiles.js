import { api } from "./client";

const base = (id) => `/faculty/${id}`;

export const profilesApi = {
  get: (id) => api.get(`${base(id)}/profile-data`).then((r) => r.data),
  save: (id, body) => api.put(`${base(id)}/profile-data`, body).then((r) => r.data),
  importOrcid: (id, orcid) =>
    api.post(`${base(id)}/import/orcid`, { orcid }, { timeout: 90000 }).then((r) => r.data),
  searchS2: (id, q) =>
    api
      .get(`${base(id)}/semantic-scholar/search`, { params: { q }, timeout: 60000 })
      .then((r) => r.data),
  importS2: (id, author) =>
    api
      .post(`${base(id)}/import/semantic-scholar`, { author }, { timeout: 120000 })
      .then((r) => r.data),
  decide: (id, accept, reject) =>
    api.post(`${base(id)}/imports/bulk`, { accept, reject }).then((r) => r.data),
  generate: (id) =>
    api.post(`${base(id)}/profile/generate`, null, { timeout: 120000 }).then((r) => r.data),
  versions: (id) => api.get(`${base(id)}/profile/versions`).then((r) => r.data),
  editVersion: (id, version, fields) =>
    api.put(`${base(id)}/profile/versions/${version}`, fields).then((r) => r.data),
  approve: (id, version) =>
    api.post(`${base(id)}/profile/versions/${version}/approve`).then((r) => r.data),
  overview: (id, params) => api.get(`${base(id)}/overview`, { params }).then((r) => r.data),
  evidence: (id, ids) =>
    api.get(`${base(id)}/evidence`, { params: { ids: ids.join(",") } }).then((r) => r.data),
};

/** How a generated text was written, in words for the page. */
export function engineLabel(engine) {
  if (!engine) return "";
  if (engine.startsWith("groq:")) return `Written by Groq (${engine.slice(5)})`;
  if (engine === "template") return "Written from a fixed template (no AI model configured)";
  return "Built from the feedback statistics (no AI model configured)";
}

/** The editable part of a profile, as sent to PUT. */
export function editable(profile) {
  return {
    designation: profile.designation ?? "",
    photo_url: profile.photo_url ?? "",
    interests: profile.interests ?? [],
    qualifications: profile.qualifications ?? [],
    experience: profile.experience ?? [],
    publications: profile.publications ?? [],
    achievements: profile.achievements ?? [],
  };
}

/** Empty strings become null and numbers are parsed, so the API sees clean values. */
export function toPayload(form) {
  const clean = (v) => (typeof v === "string" ? v.trim() || null : v);
  const year = (v) => (v === "" || v === null || v === undefined ? null : Number(v));
  const item = (obj, years = []) =>
    Object.fromEntries(
      Object.entries(obj).map(([k, v]) => [k, years.includes(k) ? year(v) : clean(v)]),
    );
  return {
    designation: clean(form.designation),
    photo_url: clean(form.photo_url),
    interests: form.interests,
    qualifications: form.qualifications.map((q) => item(q, ["year"])),
    experience: form.experience.map((e) => item(e, ["from_year", "to_year"])),
    publications: form.publications.map((p) => ({
      ...item(p, ["year", "citations"]),
      authors: p.authors ?? [],
      type: p.type || "other",
    })),
    achievements: form.achievements.map((a) => item(a, ["year"])),
  };
}
