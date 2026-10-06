"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type AnalyticsDashboard, type OverviewMetrics } from "@/lib/api";

export function useOverview() {
  return useQuery<OverviewMetrics>({
    queryKey: ["analytics", "overview"],
    queryFn: () => api.get<OverviewMetrics>("/analytics/overview"),
  });
}

export function useAnalyticsDashboard(days = 30) {
  return useQuery<AnalyticsDashboard>({
    queryKey: ["analytics", "dashboard", days],
    queryFn: () => api.get<AnalyticsDashboard>(`/analytics/dashboard?days=${days}`),
  });
}