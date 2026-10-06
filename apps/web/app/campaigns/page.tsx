"use client";

import Link from "next/link";
import { Phone, Plus } from "lucide-react";

import { DashboardLayout } from "@/components/dashboard-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useCampaignAction, useCampaigns } from "@/hooks/use-campaigns";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-secondary text-secondary-foreground",
  SCHEDULED: "bg-amber-100 text-amber-700",
  RUNNING: "bg-emerald-100 text-emerald-700",
  PAUSED: "bg-amber-100 text-amber-700",
  COMPLETED: "bg-blue-100 text-blue-700",
  CANCELLED: "bg-gray-100 text-gray-600",
};

export default function CampaignsPage() {
  const { data: campaigns, isLoading, isError } = useCampaigns();
  const campaignAction = useCampaignAction();

  const runAction = (id: string, act: string) =>
    campaignAction.mutate({ id, action: act });

  return (
    <DashboardLayout>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Campaigns</h1>
        <Link href="/campaigns/new">
          <Button>
            <Plus className="h-4 w-4" /> New Campaign
          </Button>
        </Link>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading campaigns…</p>
      ) : isError ? (
        <p className="text-destructive">Unable to load campaigns.</p>
      ) : !campaigns?.length ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <Phone className="h-10 w-10 text-muted-foreground" />
            <p className="text-muted-foreground">
              No campaigns yet. Create one to start calling leads.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-secondary/50">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Name</th>
                <th className="px-4 py-2 text-left font-medium">Status</th>
                <th className="px-4 py-2 text-left font-medium">Leads</th>
                <th className="px-4 py-2 text-left font-medium">Concurrency</th>
                <th className="px-4 py-2 text-left font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {campaigns.map((campaign) => (
                <tr key={campaign.id} className="hover:bg-secondary/30">
                  <td className="px-4 py-2 font-medium">
                    <Link href={`/campaigns/${campaign.id}`} className="hover:text-primary">
                      {campaign.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${
                        STATUS_COLORS[campaign.status] ?? "bg-secondary"
                      }`}
                    >
                      {campaign.status}
                    </span>
                  </td>
                  <td className="px-4 py-2">{campaign.lead_count}</td>
                  <td className="px-4 py-2">{campaign.max_concurrent_calls}</td>
                  <td className="px-4 py-2">
                    <div className="flex gap-2">
                      {campaign.status === "DRAFT" && (
                        <Button size="sm" variant="outline" onClick={() => runAction(campaign.id, "start")}>
                          Start
                        </Button>
                      )}
                      {campaign.status === "RUNNING" && (
                        <Button size="sm" variant="outline" onClick={() => runAction(campaign.id, "pause")}>
                          Pause
                        </Button>
                      )}
                      {campaign.status === "PAUSED" && (
                        <Button size="sm" variant="outline" onClick={() => runAction(campaign.id, "start")}>
                          Resume
                        </Button>
                      )}
                      {(campaign.status === "RUNNING" || campaign.status === "PAUSED") && (
                        <Button size="sm" variant="ghost" onClick={() => runAction(campaign.id, "cancel")}>
                          Cancel
                        </Button>
                      )}
                    </div>
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