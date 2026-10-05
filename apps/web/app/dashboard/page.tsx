"use client";

import {
  Banknote,
  CheckCircle2,
  Phone,
  PhoneCall,
  ThumbsDown,
  Users,
  XCircle,
} from "lucide-react";

import { DashboardLayout } from "@/components/dashboard-layout";
import { KpiCard } from "@/components/kpi-card";
import { useOverview } from "@/hooks/use-dashboard";
import { cn } from "@/lib/utils";

function formatDuration(seconds: number): string {
  if (!seconds) return "0s";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export default function DashboardPage() {
  const { data, isLoading, isError } = useOverview();

  return (
    <DashboardLayout>
      <h1 className="mb-6 text-2xl font-semibold">Dashboard</h1>

      {isLoading ? (
        <p className="text-muted-foreground">Loading metrics…</p>
      ) : isError || !data ? (
        <p className="text-destructive">Unable to load metrics. Check the API connection.</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard label="Leads" value={data.total_leads} icon={<Users className="h-4 w-4" />} />
          <KpiCard label="Total Calls" value={data.total_calls} icon={<Phone className="h-4 w-4" />} />
          <KpiCard
            label="Completed"
            value={data.completed_calls}
            icon={<CheckCircle2 className="h-4 w-4 text-emerald-500" />}
          />
          <KpiCard
            label="Failed"
            value={data.failed_calls}
            icon={<XCircle className="h-4 w-4 text-red-500" />}
          />
          <KpiCard
            label="Interested"
            value={data.interested}
            icon={<ThumbsDown className="h-4 w-4 rotate-180 text-emerald-500" />}
          />
          <KpiCard
            label="Not Interested"
            value={data.not_interested}
            icon={<ThumbsDown className="h-4 w-4 text-red-500" />}
          />
          <KpiCard
            label="Callback Requested"
            value={data.callback_requested}
            icon={<PhoneCall className="h-4 w-4 text-blue-500" />}
          />
          <KpiCard
            label="Avg Duration"
            value={formatDuration(data.average_call_duration_seconds)}
            icon={<Banknote className="h-4 w-4" />}
          />
        </div>
      )}
    </DashboardLayout>
  );
}