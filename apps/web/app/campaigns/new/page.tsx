"use client";

import { CampaignForm } from "@/components/campaign-form";
import { DashboardLayout } from "@/components/dashboard-layout";

export default function NewCampaignPage() {
  return (
    <DashboardLayout>
      <h1 className="mb-6 text-2xl font-semibold">Create Campaign</h1>
      <CampaignForm />
    </DashboardLayout>
  );
}
