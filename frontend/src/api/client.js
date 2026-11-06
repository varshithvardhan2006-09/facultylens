import axios from "axios";

/**
 * Shared Axios instance. Vite proxies /api to the FastAPI server in development, so the
 * refresh cookie (httpOnly, path /api/auth) is same-origin.
 *
 * The access token lives only in memory (never localStorage). On a 401 the client asks
 * /auth/refresh once for a new token and retries; concurrent 401s share that one refresh.
 */
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? "/api",
  timeout: 15000,
  withCredentials: true,
});

let accessToken = null;
let refreshing = null;
const handlers = { onSessionLost: () => {}, onPasswordChangeRequired: () => {} };

export function setAccessToken(token) {
  accessToken = token;
}

export function setAuthHandlers(next) {
  Object.assign(handlers, next);
}

/** Ask for a new access token using the refresh cookie. Resolves to the token response or null. */
export function refreshSession() {
  if (!refreshing) {
    refreshing = api
      .post("/auth/refresh", null, { _skipAuthRetry: true })
      .then((res) => {
        if (res.status === 204) {
          accessToken = null; // no session cookie: signed out
          return null;
        }
        accessToken = res.data.access_token;
        return res.data;
      })
      .catch(() => {
        accessToken = null;
        return null;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const { config, response } = error;
    if (!response || !config) throw error;
    if (response.status === 401 && !config._skipAuthRetry && !config._retried) {
      const session = await refreshSession();
      if (session) {
        config._retried = true;
        return api(config);
      }
      handlers.onSessionLost();
    }
    if (response.status === 403 && response.data?.detail?.code === "password_change_required") {
      handlers.onPasswordChangeRequired();
    }
    throw error;
  },
);

/** Turn any FastAPI error shape into one readable sentence. */
export function errorMessage(error, fallback = "Something went wrong. Try again.") {
  if (!error?.response) {
    return error?.code === "ECONNABORTED"
      ? "The server took too long to answer. Try again."
      : "Can't reach the server. Check that the API is running.";
  }
  const detail = error.response.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d) => d.msg?.replace(/^Value error, /, "")).join(" ");
  }
  if (error.response.status === 429) return "Too many attempts. Wait a minute and try again.";
  return fallback;
}

/** GET /health. A 503 still carries a JSON body describing what is down, so return it. */
export async function getHealth() {
  const res = await api.get("/health", { validateStatus: (s) => s === 200 || s === 503 });
  return res.data;
}

export async function getModelHealth() {
  const res = await api.get("/health/models");
  return res.data;
}
