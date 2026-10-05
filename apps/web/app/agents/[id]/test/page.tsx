"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Send } from "lucide-react";

import { DashboardLayout } from "@/components/dashboard-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAgent } from "@/hooks/use-agents";
import { cn } from "@/lib/utils";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export default function AgentTestPage() {
  const { id } = useParams<{ id: string }>();
  const { data: agent } = useAgent(id);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");

  const chatMutation = useMutation({
    mutationFn: async (userText: string) => {
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      const res = await api.post<{ reply: string }>("/agents/chat", {
        agent_id: id,
        messages: [...history, { role: "user", content: userText }],
      });
      return res.reply;
    },
    onSuccess: (reply, userText) => {
      setMessages((prev) => [
        ...prev,
        { role: "user", content: userText },
        { role: "assistant", content: reply },
      ]);
    },
  });

  const send = () => {
    if (!draft.trim() || chatMutation.isPending) return;
    const text = draft.trim();
    setDraft("");
    // Optimistically show the user message, then the assistant reply on success.
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    chatMutation.mutate(text);
  };

  return (
    <DashboardLayout>
      <h1 className="mb-2 text-2xl font-semibold">Test Agent</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        {agent ? agent.name : "Agent"} — test the conversation before launching a campaign.
      </p>

      <Card className="mx-auto max-w-2xl">
        <CardHeader>
          <CardTitle>Conversation</CardTitle>
        </CardHeader>
        <CardContent className="flex h-[420px] flex-col justify-end gap-3">
          <div className="flex flex-col gap-3 overflow-y-auto">
            {messages.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                Type a message to start chatting with the agent.
              </p>
            ) : (
              messages.map((m, i) => (
                <div
                  key={i}
                  className={cn(
                    "max-w-[80%] rounded-lg px-3 py-2 text-sm",
                    m.role === "assistant"
                      ? "self-start bg-secondary text-secondary-foreground"
                      : "self-end bg-primary text-primary-foreground",
                  )}
                >
                  {m.content}
                </div>
              ))
            )}
            {chatMutation.isPending && (
              <div className="self-start rounded-lg bg-secondary px-3 py-2 text-sm text-muted-foreground">
                …
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              placeholder="Type message…"
              disabled={chatMutation.isPending}
            />
            <Button onClick={send} disabled={chatMutation.isPending || !draft.trim()}>
              <Send className="h-4 w-4" /> Send
            </Button>
          </div>
          {chatMutation.isError && (
            <p className="text-sm text-destructive">
              {(chatMutation.error as Error)?.message ?? "Request failed"}
            </p>
          )}
        </CardContent>
      </Card>
    </DashboardLayout>
  );
}