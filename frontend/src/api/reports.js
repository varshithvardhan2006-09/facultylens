import { api } from "./client";

const base = (cycle) => `/reports/feedback/${cycle}`;

export const reportsApi = {
  status: (cycle) => api.get(`${base(cycle)}/status`).then((r) => r.data),
  actions: (cycle) => api.get(`${base(cycle)}/actions`).then((r) => r.data),
  draft: (cycle) => api.post(`${base(cycle)}/draft`, null, { timeout: 120000 }).then((r) => r.data),
  add: (cycle, body) => api.post(`${base(cycle)}/actions`, body).then((r) => r.data),
  edit: (cycle, id, body) => api.put(`${base(cycle)}/actions/${id}`, body).then((r) => r.data),
  remove: (cycle, id) => api.delete(`${base(cycle)}/actions/${id}`),
  evidence: (cycle, id) => api.get(`${base(cycle)}/actions/${id}/evidence`).then((r) => r.data),

  /** Fetch the file with the session's token and hand it to the browser as a download. */
  async download(cycle, format, draft) {
    const response = await api.get(`${base(cycle)}.${format}`, {
      params: draft ? { draft: true } : {},
      responseType: "blob",
      timeout: 120000,
    });
    const disposition = response.headers["content-disposition"] ?? "";
    const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? `Feedback-report.${format}`;
    const url = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return name;
  },
};

/** Error text from a blob response (a failed download still carries a JSON detail). */
export async function blobError(err, fallback) {
  const data = err?.response?.data;
  if (data instanceof Blob) {
    try {
      const detail = JSON.parse(await data.text()).detail;
      return (typeof detail === "string" ? detail : detail?.message) ?? fallback;
    } catch {
      return fallback;
    }
  }
  return fallback;
}
