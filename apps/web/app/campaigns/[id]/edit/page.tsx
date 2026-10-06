"use client";

import { useParams } from "next/navigation";

import { CampaignForm } from "@/components/campaign-form";
import { DashboardLayout } from "@/components/dashboard-layout";
import { useCampaigns } from "@/hooks/use-campaigns";

export default function CampaignEditPage() {
  const { id } = useParams<{ id: string }>();
  const { data: campaigns } = useCampaigns();
  const campaign = campaigns?.find((c) => c.id === id);
  return (
    <DashboardLayout>
      <h1 className="mb-6 text-2xl font-semibold">Edit Campaign</h1>
      {campaign ? <CampaignForm campaign={campaign} /> : <p className="text-muted-foreground">Campaign not found.</p>}
    </DashboardLayout>
  );
}