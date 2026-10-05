"use client";

import { useParams } from "next/navigation";

import { DashboardLayout } from "@/components/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export default function LeadDetailPage() {
  const { id } = useParams<{ id: string }>();
  const lead = useQuery({
    queryKey: ["leads", id],
    queryFn: () => api.get(`/leads/${id}`),
    enabled: Boolean(id),
  });

  if (lead.isLoading) return <DashboardLayout><p className="text-muted-foreground">Loading…</p></DashboardLayout>;
  if (lead.isError || !lead.data)
    return <DashboardLayout><p className="text-destructive">Lead not found.</p></DashboardLayout>;

  const data = lead.data as {
    name?: string | null;
    phone_number: string;
    email?: string | null;
    location?: string | null;
    language?: string | null;
    status: string;
    custom_fields: Record<string, unknown>;
  };

  return (
    <DashboardLayout>
      <h1 className="mb-6 text-2xl font-semibold">
        {data.name || "Lead"} <span className="text-muted-foreground">· {data.phone_number}</span>
      </h1>
      <Card>
        <CardHeader>
          <CardTitle>Customer Information</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm sm:grid-cols-2">
          <div><Label>Name</Label><p>{data.name || "—"}</p></div>
          <div><Label>Phone</Label><p>{data.phone_number}</p></div>
          <div><Label>Email</Label><p>{data.email || "—"}</p></div>
          <div><Label>Location</Label><p>{data.location || "—"}</p></div>
          <div><Label>Language</Label><p>{data.language || "auto"}</p></div>
          <div><Label>Status</Label><p>{data.status}</p></div>
        </CardContent>
      </Card>
      <div className="mt-6"><p className="text-sm text-muted-foreground">
        Call history and customer insights will appear here.
      </p></div>
    </DashboardLayout>
  );
}