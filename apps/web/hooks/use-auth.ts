"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, clearTokens, setTokens, type TokenPair } from "@/lib/api";

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (credentials: { email: string; password: string }) =>
      api.post<TokenPair>("/auth/login", credentials),
    onSuccess: (tokens) => {
      setTokens(tokens.access_token, tokens.refresh_token);
      qc.clear();
    },
  });
}

export function useRegister() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { email: string; password: string; name: string }) =>
      api.post<TokenPair>("/auth/register", payload),
    onSuccess: (tokens) => {
      setTokens(tokens.access_token, tokens.refresh_token);
      qc.clear();
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => {
      const refresh = localStorage.getItem("nenu_refresh_token");
      return refresh
        ? api.post("/auth/logout", { refresh_token: refresh }).catch(() => undefined)
        : Promise.resolve(undefined);
    },
    onSettled: () => {
      clearTokens();
      qc.clear();
    },
  });
}

export function useCurrentUser() {
  return useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => api.get<{ id: string; email: string; name: string }>("/auth/me"),
    retry: false,
  });
}