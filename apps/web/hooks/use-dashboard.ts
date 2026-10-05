"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type OverviewMetrics } from "@/lib/api";

export function useOverview() {
  return useQuery<OverviewMetrics>({
    queryKey: ["analytics", "overview"],
    queryFn: () => api.get<OverviewMetrics>("/analytics/overview"),
  });
}

export function useMe() {
  return useQuery<{ id: string; email: string; name: string }>({
    queryKey: ["auth", "me"],
    queryFn: () => api.get("/auth/me"),
    retry: false,
  });
}