"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { Phone, Upload, Users } from "lucide-react";

import { DashboardLayout } from "@/components/dashboard-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useImportLeads, useLeads } from "@/hooks/use-leads";

const STATUS_COLORS: Record<string, string> = {
  NEW: "bg-secondary text-secondary-foreground",
  CALLING: "bg-blue-100 text-blue-700",
  COMPLETED: "bg-emerald-100 text-emerald-700",
  FAILED: "bg-red-100 text-red-700",
  INTERESTED: "bg-emerald-100 text-emerald-700",
  NOT_INTERESTED: "bg-red-100 text-red-700",
  CALLBACK_REQUESTED: "bg-blue-100 text-blue-700",
  DO_NOT_CALL: "bg-gray-100 text-gray-600",
};

export default function LeadsPage() {
  const { data: leads, isLoading, isError } = useLeads();
  const importLead = useImportLeads();
  const fileRef = useRef<HTMLInputElement>(null);
  const [result, setResult] = useState<string | null>(null);

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    try {
      const res = await importLead.mutateAsync(file);
      setResult(
        `Imported ${res.imported} / ${res.total_rows}; ${res.duplicates} duplicates, ${res.invalid} invalid`,
      );
    } catch (e) {
      setResult(`Import failed: ${(e as Error).message}`);
    }
  };

  return (
    <DashboardLayout>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Leads</h1>
        <div className="flex gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => onFile(e.target.files?.[0])}
          />
          <Button variant="outline" onClick={() => fileRef.current?.click()}>
            <Upload className="h-4 w-4" /> Import CSV
          </Button>
          <Link href="/leads/new">
            <Button>
              <Users className="h-4 w-4" /> Add Lead
            </Button>
          </Link>
        </div>
      </div>

      {result && (
        <div className="mb-4 rounded border border-blue-200 bg-blue-50 p-3 text-sm">
          {result}
        </div>
      )}

      {isLoading ? (
        <p className="text-muted-foreground">Loading leads…</p>
      ) : isError ? (
        <p className="text-destructive">Unable to load leads.</p>
      ) : !leads?.length ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <Phone className="h-10 w-10 text-muted-foreground" />
            <p className="text-muted-foreground">
              No leads yet. Import a CSV or add a lead manually.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-secondary/50">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Name</th>
                <th className="px-4 py-2 text-left font-medium">Phone</th>
                <th className="px-4 py-2 text-left font-medium">Location</th>
                <th className="px-4 py-2 text-left font-medium">Language</th>
                <th className="px-4 py-2 text-left font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {leads.map((lead) => (
                <tr key={lead.id} className="hover:bg-secondary/30">
                  <td className="px-4 py-2 font-medium">
                    <Link href={`/leads/${lead.id}`} className="hover:text-primary">
                      {lead.name || "—"}
                    </Link>
                  </td>
                  <td className="px-4 py-2">{lead.phone_number}</td>
                  <td className="px-4 py-2">{lead.location || "—"}</td>
                  <td className="px-4 py-2">{lead.language || "auto"}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${
                        STATUS_COLORS[lead.status] ?? "bg-secondary"
                      }`}
                    >
                      {lead.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </DashboardLayout>
  );
}