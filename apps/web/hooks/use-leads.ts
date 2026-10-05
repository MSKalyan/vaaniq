"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";

export interface Lead {
  id: string;
  name?: string | null;
  phone_number: string;
  email?: string | null;
  language?: string | null;
  location?: string | null;
  status: string;
  custom_fields: Record<string, unknown>;
  created_at: string;
}

export interface ImportResult {
  job_id: string;
  filename: string;
  total_rows: number;
  imported: number;
  duplicates: number;
  invalid: number;
  status: string;
  errors: Record<string, unknown>[];
}

export function useLeads(status?: string) {
  return useQuery<Lead[]>({
    queryKey: ["leads", status ?? "all"],
    queryFn: () => {
      const qs = status ? `?status=${status}` : "";
      return api.get<Lead[]>(`/leads${qs}`);
    },
  });
}

export function useImportLeads() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const token =
        typeof window !== "undefined"
          ? localStorage.getItem("nenu_access_token")
          : null;
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/leads/import`,
        {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: form,
        },
      );
      if (!res.ok) throw new Error((await res.json()).detail ?? "Import failed");
      return (await res.json()) as ImportResult;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leads"] }),
  });
}