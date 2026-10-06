"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  api,
  type CallAnalysis,
  type CallDetail,
  type CallsPage,
  type TranscriptTurn,
} from "@/lib/api";

export function useCalls(params: { limit?: number; offset?: number; outcome?: string } = {}) {
  const { limit = 50, offset = 0, outcome } = params;
  const search = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (outcome) search.set("outcome", outcome);

  return useQuery<CallsPage>({
    queryKey: ["calls", { limit, offset, outcome }],
    queryFn: () => api.get<CallsPage>(`/calls?${search.toString()}`),
  });
}

export function useCall(callId: string | null) {
  return useQuery<CallDetail>({
    queryKey: ["calls", callId],
    queryFn: () => api.get<CallDetail>(`/calls/${callId}`),
    enabled: Boolean(callId),
  });
}

export function useTranscript(callId: string | null) {
  return useQuery<{ call_id: string; duration_seconds: number | null; turns: TranscriptTurn[] }>({
    queryKey: ["calls", callId, "transcript"],
    queryFn: () =>
      api.get(`/calls/${callId}/transcript`),
    enabled: Boolean(callId),
  });
}

export function useAnalysis(callId: string | null) {
  return useQuery<CallAnalysis | null>({
    queryKey: ["calls", callId, "analysis"],
    queryFn: () => api.get<CallAnalysis>(`/calls/${callId}/analysis`),
    enabled: Boolean(callId),
  });
}

/** Post-call analysis is generated on demand; this triggers (or re-triggers) it. */
export function useRunAnalysis(callId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<CallAnalysis>(`/calls/${callId}/analyze`),
    onSuccess: (analysis) => {
      qc.setQueryData(["calls", callId, "analysis"], analysis);
      void qc.invalidateQueries({ queryKey: ["calls", callId] });
    },
  });
}

export function useEndCall() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (callId: string) => api.post<CallDetail>(`/calls/${callId}/end`),
    onSuccess: (_data, callId) => {
      void qc.invalidateQueries({ queryKey: ["calls", callId] });
      void qc.invalidateQueries({ queryKey: ["calls"] });
    },
  });
}