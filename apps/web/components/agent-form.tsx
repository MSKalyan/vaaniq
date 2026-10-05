"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useRouter } from "next/navigation";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input, Label, Textarea } from "@/components/ui/input";
import { SUPPORTED_LANGUAGES } from "@nenuaikadu/shared";
import { useCreateAgent, useUpdateAgent } from "@/hooks/use-agents";
import type { Agent } from "@/types/agent";

const schema = z.object({
  name: z.string().min(1, "Name is required").max(120),
  description: z.string().max(2000).optional(),
  system_prompt: z.string().max(20000).optional(),
  language: z.string(),
  voice: z.string().optional(),
  greeting: z.string().max(2000).optional(),
  max_call_duration: z.coerce.number().min(30).max(7200).default(600),
  temperature: z.coerce.number().min(0).max(2).default(0.7),
});

type FormValues = z.infer<typeof schema>;

export function AgentForm({ agent }: { agent?: Agent }) {
  const router = useRouter();
  const createAgent = useCreateAgent();
  const updateAgent = useUpdateAgent(agent?.id ?? "");

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: agent
      ? {
          name: agent.name,
          description: agent.description ?? "",
          system_prompt: agent.system_prompt,
          language: agent.language,
          voice: agent.voice ?? "",
          greeting: agent.greeting ?? "",
          max_call_duration: agent.max_call_duration,
          temperature: agent.temperature,
        }
      : {
          name: "",
          description: "",
          system_prompt: "",
          language: "auto",
          voice: "",
          greeting: "",
          max_call_duration: 600,
          temperature: 0.7,
        },
  });

  const onSubmit = async (values: FormValues) => {
    if (agent) {
      await updateAgent.mutateAsync(values);
    } else {
      await createAgent.mutateAsync(values);
    }
    router.push("/agents");
    router.refresh();
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="grid max-w-2xl gap-5">
      <div>
        <Label htmlFor="name">Agent name</Label>
        <Input id="name" {...register("name")} />
        {errors.name && <p className="mt-1 text-sm text-destructive">{errors.name.message}</p>}
      </div>

      <div>
        <Label htmlFor="description">Description</Label>
        <Textarea id="description" {...register("description")} rows={2} />
      </div>

      <div>
        <Label htmlFor="system_prompt">System prompt / instructions</Label>
        <Textarea id="system_prompt" {...register("system_prompt")} rows={8} className="min-h-[180px] font-mono text-xs" />
        <p className="mt-1 text-xs text-muted-foreground">
          Set the agent&apos;s identity, objective, and conversation rules.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="language">Language</Label>
          <select id="language" {...register("language")} className="flex h-9 w-full rounded-md border border-border bg-background px-3 text-sm">
            {SUPPORTED_LANGUAGES.map((lang) => (
              <option key={lang} value={lang}>
                {lang}
              </option>
            ))}
          </select>
        </div>
        <div>
          <Label htmlFor="voice">Voice</Label>
          <Input id="voice" {...register("voice")} placeholder="Select a voice" />
        </div>
      </div>

      <div>
        <Label htmlFor="greeting">Greeting</Label>
        <Textarea id="greeting" {...register("greeting")} rows={2} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="max_call_duration">Max call duration (s)</Label>
          <Input id="max_call_duration" type="number" {...register("max_call_duration")} />
        </div>
        <div>
          <Label htmlFor="temperature">Temperature</Label>
          <Input id="temperature" type="number" step="0.1" {...register("temperature")} />
        </div>
      </div>

      <div className="flex gap-3">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : agent ? "Save changes" : "Create agent"}
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => router.push("/agents")}
        >
          Cancel
        </Button>
      </div>
    </form>
  );
}