import axios from "axios";
import { useAuthStore } from "@/features/auth/store";

/** Empty string = same-origin (nginx proxies /api). Dev default = localhost API. */
const raw = import.meta.env.VITE_API_URL as string | undefined;
const API_URL =
  raw !== undefined && raw !== ""
    ? raw.replace(/\/$/, "")
    : import.meta.env.PROD
      ? ""
      : "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().access;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshing: Promise<string | null> | null = null;

apiClient.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error);
    }
    original._retry = true;
    const { refresh, setTokens, logout } = useAuthStore.getState();
    if (!refresh) {
      logout();
      return Promise.reject(error);
    }
    if (!refreshing) {
      refreshing = axios
        .post(`${API_URL}/api/v1/auth/refresh/`, { refresh })
        .then((res) => {
          setTokens(res.data.access, res.data.refresh ?? refresh);
          return res.data.access as string;
        })
        .catch(() => {
          logout();
          return null;
        })
        .finally(() => {
          refreshing = null;
        });
    }
    const access = await refreshing;
    if (!access) return Promise.reject(error);
    original.headers.Authorization = `Bearer ${access}`;
    return apiClient(original);
  },
);

export async function healthCheck() {
  const res = await axios.get(`${API_URL}/api/health/`);
  return res.data;
}
