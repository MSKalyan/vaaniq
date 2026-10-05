"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";

export interface Campaign {
  id: string;
  user_id: string;
  name: string;
  agent_id: string;
  status: string;
  start_time?: string | null;
  end_time?: string | null;
  max_concurrent_calls: number;
  retry_attempts: number;
  retry_delay_minutes: number;
  lead_count: number;
  created_at: string;
}

export interface CampaignCreate {
  name: string;
  agent_id: string;
  lead_ids: string[];
  max_concurrent_calls?: number;
  retry_attempts?: number;
  retry_delay_minutes?: number;
}

export function useCampaigns() {
  return useQuery<Campaign[]>({
    queryKey: ["campaigns"],
    queryFn: () => api.get<Campaign[]>("/campaigns"),
  });
}

export function useCreateCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CampaignCreate) =>
      api.post<Campaign>("/campaigns", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["campaigns"] }),
  });
}

export function useCampaignAction(campaignId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (action: string) =>
      api.post<Campaign>(`/campaigns/${campaignId}/${action}`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["campaigns"] }),
  });
}