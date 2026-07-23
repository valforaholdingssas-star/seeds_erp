import { apiClient } from "@/lib/apiClient";
import type { AuthUser } from "@/features/auth/store";

export async function loginRequest(email: string, password: string) {
  const { data } = await apiClient.post<{
    access: string;
    refresh: string;
    user: AuthUser;
  }>("/auth/login/", { email, password });
  return data;
}

export async function fetchMe() {
  const { data } = await apiClient.get<AuthUser>("/auth/me/");
  return data;
}
