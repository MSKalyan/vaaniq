"use client";

import { AgentForm } from "@/components/agent-form";
import { DashboardLayout } from "@/components/dashboard-layout";

export default function NewAgentPage() {
  return (
    <DashboardLayout>
      <h1 className="mb-6 text-2xl font-semibold">Create AI Agent</h1>
      <AgentForm />
    </DashboardLayout>
  );
}