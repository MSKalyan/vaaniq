"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type SettingsPayload, type Voice } from "@/lib/api";

export function useSettings() {
  return useQuery<SettingsPayload>({
    queryKey: ["settings"],
    queryFn: () => api.get<SettingsPayload>("/settings"),
  });
}

export function useVoices(provider?: string) {
  const search = provider ? `?provider=${encodeURIComponent(provider)}` : "";
  return useQuery<Voice[]>({
    queryKey: ["voices", provider ?? "all"],
    queryFn: () => api.get<Voice[]>(`/settings/voices${search}`),
  });
}