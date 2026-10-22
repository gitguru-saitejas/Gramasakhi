import axios from "axios";
import { resolveAdminApiBaseUrl } from "../../services/api-config";

export const apiEvents = {
  listeners: {},
  subscribe(event, callback) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(callback);
    return () => {
      this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
    };
  },
  emit(event, data) {
    if (this.listeners[event]) {
      this.listeners[event].forEach(cb => cb(data));
    }
  }
};

const api = axios.create({
  baseURL: resolveAdminApiBaseUrl(),
  timeout: 30000, // Large timeout for file upload text extraction processing
  headers: {
    "Content-Type": "application/json",
  }
});

// Request Interceptor to attach JWT token
api.interceptors.request.use(
  (config) => {
    apiEvents.emit("loading", true);
    const token = localStorage.getItem("superAdminToken");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    apiEvents.emit("loading", false);
    return Promise.reject(error);
  }
);

// Response Interceptor for global success / error feedback
api.interceptors.response.use(
  (response) => {
    apiEvents.emit("loading", false);
    return response;
  },
  (error) => {
    apiEvents.emit("loading", false);
    const msg = error.response?.data?.detail 
      || error.response?.data?.message 
      || error.message 
      || "An unexpected error occurred.";
    apiEvents.emit("toast", { type: "error", message: msg });
    return Promise.reject(error);
  }
);

export default api;
