"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { DashboardLayout } from "@/components/dashboard-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCampaigns, useCampaignAction } from "@/hooks/use-campaigns";

export default function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: campaigns } = useCampaigns();
  const campaignAction = useCampaignAction();
  const campaign = campaigns?.find((c) => c.id === id);
  if (!campaign) {
    return (
      <DashboardLayout>
        <p className="text-muted-foreground">Campaign not found.</p>
      </DashboardLayout>
    );
  }
  const runAction = (act: string) => campaignAction.mutate({ id: campaign.id, action: act });
  return (
    <DashboardLayout>
      <div className="mb-6 flex items-center gap-3">
        <Link href="/campaigns">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <h1 className="text-2xl font-semibold">{campaign.name}</h1>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Campaign Details</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 text-sm sm:grid-cols-2">
          <div><p className="text-muted-foreground">Status</p><p className="font-medium">{campaign.status}</p></div>
          <div><p className="text-muted-foreground">Agent ID</p><p className="font-mono text-xs">{campaign.agent_id}</p></div>
          <div><p className="text-muted-foreground">Leads enrolled</p><p className="font-medium">{campaign.lead_count}</p></div>
          <div><p className="text-muted-foreground">Max concurrent calls</p><p className="font-medium">{campaign.max_concurrent_calls}</p></div>
          <div><p className="text-muted-foreground">Retry attempts</p><p className="font-medium">{campaign.retry_attempts}</p></div>
          <div><p className="text-muted-foreground">Retry delay (mins)</p><p className="font-medium">{campaign.retry_delay_minutes}</p></div>
          <div><p className="text-muted-foreground">Created</p><p className="font-medium">{new Date(campaign.created_at).toLocaleString()}</p></div>
        </CardContent>
      </Card>
      <div className="mt-6 flex gap-2">
        {campaign.status === "DRAFT" && <Button onClick={() => runAction("start")}>Start Campaign</Button>}
        {campaign.status === "RUNNING" && <Button variant="outline" onClick={() => runAction("pause")}>Pause</Button>}
        {campaign.status === "PAUSED" && <Button variant="outline" onClick={() => runAction("start")}>Resume</Button>}
        {(campaign.status === "RUNNING" || campaign.status === "PAUSED" || campaign.status === "DRAFT") && <Button variant="ghost" onClick={() => runAction("cancel")}>Cancel</Button>}
      </div>
    </DashboardLayout>
  );
}