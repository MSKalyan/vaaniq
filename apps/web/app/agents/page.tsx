"use client";

import Link from "next/link";
import { Bot, Plus } from "lucide-react";

import { useDeleteAgent, useAgents } from "@/hooks/use-agents";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DashboardLayout } from "@/components/dashboard-layout";

export default function AgentsPage() {
  const { data: agents, isLoading, isError } = useAgents();
  const deleteAgent = useDeleteAgent();

  return (
    <DashboardLayout>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">AI Agents</h1>
        <Link href="/agents/new">
          <Button>
            <Plus className="h-4 w-4" /> New Agent
          </Button>
        </Link>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading agents…</p>
      ) : isError ? (
        <p className="text-destructive">Unable to load agents.</p>
      ) : !agents?.length ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <Bot className="h-10 w-10 text-muted-foreground" />
            <p className="text-muted-foreground">
              No agents yet. Create your first AI voice agent.
            </p>
            <Link href="/agents/new">
              <Button variant="secondary">
                <Plus className="h-4 w-4" /> Create Agent
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <Card key={agent.id}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <CardTitle>{agent.name}</CardTitle>
                  <span className="rounded bg-secondary px-2 py-0.5 text-xs text-secondary-foreground">
                    {agent.status}
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                <p className="mb-3 line-clamp-2 text-sm text-muted-foreground">
                  {agent.description || "No description"}
                </p>
                <div className="mb-4 flex items-center gap-3 text-xs">
                  <span className="rounded bg-secondary px-2 py-0.5">{agent.language}</span>
                  {agent.voice ? (
                    <span className="text-muted-foreground">Voice: {agent.voice}</span>
                  ) : null}
                </div>
                <div className="flex gap-2">
                  <Link href={`/agents/${agent.id}`}>
                    <Button variant="outline" size="sm">
                      Edit
                    </Button>
                  </Link>
                  <Link href={`/agents/${agent.id}/test`}>
                    <Button variant="outline" size="sm">
                      Test
                    </Button>
                  </Link>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="ml-auto text-destructive"
                    onClick={() => deleteAgent.mutate(agent.id)}
                  >
                    Delete
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </DashboardLayout>
  );
}