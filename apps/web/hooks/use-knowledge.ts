"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type KnowledgeBase, type KnowledgeDocument } from "@/lib/api";

export function useKnowledgeBases() {
  return useQuery<KnowledgeBase[]>({
    queryKey: ["knowledge", "bases"],
    queryFn: () => api.get<KnowledgeBase[]>("/knowledge/bases"),
  });
}

export function useKnowledgeDocuments(knowledgeBaseId: string | null) {
  return useQuery<KnowledgeDocument[]>({
    queryKey: ["knowledge", "documents", knowledgeBaseId],
    queryFn: () => api.get<KnowledgeDocument[]>(`/knowledge/bases/${knowledgeBaseId}/documents`),
    enabled: Boolean(knowledgeBaseId),
  });
}

export function useCreateKnowledgeBase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; description?: string }) =>
      api.post<KnowledgeBase>("/knowledge/bases", payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["knowledge", "bases"] });
    },
  });
}

export function useDeleteKnowledgeBase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (knowledgeBaseId: string) => api.delete(`/knowledge/bases/${knowledgeBaseId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["knowledge"] });
    },
  });
}

export function useCreateKnowledgeDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      knowledge_base_id: string;
      title: string;
      content: string;
      source_type?: string;
    }) =>
      api.post<KnowledgeDocument>(
        `/knowledge/bases/${payload.knowledge_base_id}/documents`,
        payload,
      ),
    onSuccess: (document) => {
      void qc.invalidateQueries({ queryKey: ["knowledge", "documents", document.knowledge_base_id] });
    },
  });
}

export function useDeleteKnowledgeDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) => api.delete(`/knowledge/documents/${documentId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["knowledge", "documents"] });
    },
  });
}

export function useKnowledgeSearch(query: string, knowledgeBaseIds: string[] = []) {
  const search = new URLSearchParams({ q: query });
  knowledgeBaseIds.forEach((id) => search.append("kb_id", id));
  const key = search.toString();

  return useQuery({
    queryKey: ["knowledge", "search", key],
    queryFn: () =>
      api.get<{
        query: string;
        hits: { chunk_id: string; content: string; title: string | null; score: number }[];
      }>(`/knowledge/search?${key}`),
    enabled: query.trim().length > 0,
  });
}