"use client";

import Link from "next/link";
import { useState } from "react";
import { PhoneCall } from "lucide-react";

import { DashboardLayout } from "@/components/dashboard-layout";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useCalls } from "@/hooks/use-calls";

const OUTCOMES = [
  "INTERESTED",
  "NOT_INTERESTED",
  "CALLBACK_REQUESTED",
  "NO_ANSWER",
  "BUSY",
  "FAILED",
  "DO_NOT_CALL",
];

function formatDuration(seconds: number | null): string {
  if (seconds === null) return "—";
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

export default function CallsPage() {
  const [search, setSearch] = useState("");
  const [outcome, setOutcome] = useState("");
  const calls = useCalls({ outcome: outcome || undefined });

  const items = (calls.data?.items ?? []).filter((call) => {
    const term = search.trim().toLowerCase();
    if (!term) return true;
    return (
      (call.lead_name ?? "").toLowerCase().includes(term) ||
      (call.phone_number ?? "").toLowerCase().includes(term) ||
      (call.agent_name ?? "").toLowerCase().includes(term)
    );
  });

  return (
    <DashboardLayout>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Calls</h1>
        <div className="flex gap-2">
          <Input
            className="w-56"
            placeholder="Search lead, number, agent"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <select
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
            value={outcome}
            onChange={(event) => setOutcome(event.target.value)}
          >
            <option value="">All outcomes</option>
            {OUTCOMES.map((value) => (
              <option key={value} value={value}>
                {value.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>
      </div>

      {calls.isLoading ? (
        <p className="text-muted-foreground">Loading calls…</p>
      ) : calls.isError ? (
        <p className="text-destructive">Unable to load calls.</p>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <PhoneCall className="h-10 w-10 text-muted-foreground" />
            <p className="text-muted-foreground">
              No calls yet. Start a campaign or place an ad-hoc call from a lead.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead className="border-b text-left text-muted-foreground">
                <tr>
                  <th className="p-3 font-medium">Lead</th>
                  <th className="p-3 font-medium">Number</th>
                  <th className="p-3 font-medium">Agent</th>
                  <th className="p-3 font-medium">State</th>
                  <th className="p-3 font-medium">Outcome</th>
                  <th className="p-3 font-medium">Duration</th>
                  <th className="p-3 font-medium">Started</th>
                </tr>
              </thead>
              <tbody>
                {items.map((call) => (
                  <tr key={call.id} className="border-b last:border-0 hover:bg-secondary/40">
                    <td className="p-3">
                      <Link href={`/calls/${call.id}`} className="font-medium underline">
                        {call.lead_name ?? call.lead_id.slice(0, 8)}
                      </Link>
                    </td>
                    <td className="p-3 text-muted-foreground">{call.phone_number ?? "—"}</td>
                    <td className="p-3 text-muted-foreground">{call.agent_name ?? "—"}</td>
                    <td className="p-3">{call.state}</td>
                    <td className="p-3">{call.outcome ?? "—"}</td>
                    <td className="p-3 text-muted-foreground">
                      {formatDuration(call.duration_seconds)}
                    </td>
                    <td className="p-3 text-muted-foreground">
                      {call.started_at
                        ? new Date(call.started_at).toLocaleString()
                        : new Date(call.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {calls.data && (
        <p className="mt-3 text-sm text-muted-foreground">
          Showing {items.length} of {calls.data.total} calls
        </p>
      )}
    </DashboardLayout>
  );
}