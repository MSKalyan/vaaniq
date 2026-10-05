"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { AgentForm } from "@/components/agent-form";
import { Button } from "@/components/ui/button";
import { DashboardLayout } from "@/components/dashboard-layout";
import { useAgent } from "@/hooks/use-agents";

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: agent, isLoading } = useAgent(id);

  return (
    <DashboardLayout>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">
          {isLoading ? "Loading…" : agent ? agent.name : "Agent"}
        </h1>
        <Link href={`/agents/${id}/test`}>
          <Button variant="outline">Test Agent</Button>
        </Link>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading agent…</p>
      ) : !agent ? (
        <p className="text-destructive">Agent not found.</p>
      ) : (
        <AgentForm agent={agent} />
      )}
    </DashboardLayout>
  );
}