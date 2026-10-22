import axios from "axios";
import { clearCitizenAuthMemory, getAccessToken } from "./auth-token";
import { resolveCitizenApiBaseUrl } from "./api-config";

export const apiEvents = {
  listeners: {},
  subscribe(event, callback) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(callback);
    return () => {
      this.listeners[event] = this.listeners[event].filter((cb) => cb !== callback);
    };
  },
  emit(event, data) {
    if (this.listeners[event]) {
      this.listeners[event].forEach((cb) => cb(data));
    }
  },
};

export const API_ORIGIN = resolveCitizenApiBaseUrl().replace(/\/api$/, "");

const api = axios.create({
  baseURL: resolveCitizenApiBaseUrl(),
  timeout: 0,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use(
  (config) => {
    apiEvents.emit("loading", true);
    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    if (typeof FormData !== "undefined" && config.data instanceof FormData) {
      if (config.headers && typeof config.headers.delete === "function") {
        config.headers.delete("Content-Type");
      } else if (config.headers) {
        delete config.headers["Content-Type"];
        delete config.headers["content-type"];
      }
    }
    return config;
  },
  (error) => {
    apiEvents.emit("loading", false);
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  (response) => {
    apiEvents.emit("loading", false);
    return response;
  },
  (error) => {
    apiEvents.emit("loading", false);
    const status = error?.response?.status;
    const url = String(error?.config?.url || "");
    const hadToken = Boolean(getAccessToken());
    if (status === 401 && hadToken && !url.includes("/auth/")) {
      clearCitizenAuthMemory();
      localStorage.removeItem("gramsakhiConversationId");
      sessionStorage.removeItem("gramsakhiForceNewChat");
      apiEvents.emit("auth-expired");
      if (!window.location.pathname.startsWith("/citizen/login")) {
        window.location.href = "/citizen/login";
      }
    }
    if (!error?.config?.skipErrorToast) {
      const raw = error.response?.data?.detail || error.response?.data?.message || error.message;
      const internalPattern =
        /traceback|stack trace|sqlalchemy|psycopg|sqlite|exception|\.py\b|file "|nonetype|keyerror|valueerror|attributeerror/i;
      const isSafe =
        typeof raw === "string" &&
        raw.trim() &&
        raw.length <= 200 &&
        !(status >= 500) &&
        !internalPattern.test(raw);
      const message = isSafe ? raw.trim() : "An unexpected error occurred. Please try again.";
      apiEvents.emit("toast", { type: "error", message });
    }
    return Promise.reject(error);
  }
);

function normalizeGetConfig(config) {
  if (
    config &&
    typeof config === "object" &&
    !("params" in config) &&
    !("headers" in config) &&
    !("timeout" in config)
  ) {
    return { params: config };
  }
  return config;
}

const client = {
  request: (...args) => api.request(...args),
  get: (url, config) => api.get(url, normalizeGetConfig(config)),
  post: (...args) => api.post(...args),
  put: (...args) => api.put(...args),
  patch: (...args) => api.patch(...args),
  delete: (...args) => api.delete(...args),
};

export default client;
