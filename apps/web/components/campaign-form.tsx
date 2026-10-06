"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useRouter } from "next/navigation";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { useAgents } from "@/hooks/use-agents";
import { useLeads } from "@/hooks/use-leads";
import { useCreateCampaign } from "@/hooks/use-campaigns";
import type { Campaign } from "@/hooks/use-campaigns";

const schema = z.object({
  name: z.string().min(1, "Name is required").max(120),
  agent_id: z.string().min(1, "Agent is required"),
  lead_ids: z.array(z.string()).default([]),
  max_concurrent_calls: z.coerce.number().min(1).max(100).default(5),
  retry_attempts: z.coerce.number().min(0).max(10).default(2),
  retry_delay_minutes: z.coerce.number().min(1).max(10080).default(30),
});

type FormValues = z.infer<typeof schema>;

export function CampaignForm({ campaign }: { campaign?: Campaign }) {
  const router = useRouter();
  const createCampaign = useCreateCampaign();
  const { data: agents = [] } = useAgents();
  const { data: leads = [] } = useLeads();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setValue,
    watch,
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: campaign
      ? {
          name: campaign.name,
          agent_id: campaign.agent_id,
          lead_ids: [],
          max_concurrent_calls: campaign.max_concurrent_calls,
          retry_attempts: campaign.retry_attempts,
          retry_delay_minutes: campaign.retry_delay_minutes,
        }
      : {
          name: "",
          agent_id: "",
          lead_ids: [],
          max_concurrent_calls: 5,
          retry_attempts: 2,
          retry_delay_minutes: 30,
        },
  });

  const selectedLeads = watch("lead_ids");

  const onSubmit = async (values: FormValues) => {
    if (!campaign) {
      await createCampaign.mutateAsync(values);
    }
    router.push("/campaigns");
    router.refresh();
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="grid max-w-2xl gap-5">
      <div>
        <Label htmlFor="name">Campaign name</Label>
        <Input id="name" {...register("name")} />
        {errors.name && <p className="mt-1 text-sm text-destructive">{errors.name.message}</p>}
      </div>
      <div>
        <Label htmlFor="agent_id">Agent</Label>
        <select
          id="agent_id"
          {...register("agent_id")}
          className="flex h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
        >
          <option value="">Select agent</option>
          {agents.map((agent) => (
            <option key={agent.id} value={agent.id}>
              {agent.name}
            </option>
          ))}
        </select>
        {errors.agent_id && <p className="mt-1 text-sm text-destructive">{errors.agent_id.message}</p>}
      </div>
      <div>
        <Label>Leads</Label>
        <div className="mt-2 max-h-60 overflow-y-auto rounded-md border border-border p-3">
          {leads.length === 0 ? (
            <p className="text-sm text-muted-foreground">No leads available</p>
          ) : (
            <div className="space-y-2">
              {leads.map((lead) => (
                <label key={lead.id} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    value={lead.id}
                    checked={selectedLeads?.includes(lead.id)}
                    onChange={(e) => {
                      const current = selectedLeads || [];
                      if (e.target.checked) {
                        setValue("lead_ids", [...current, lead.id]);
                      } else {
                        setValue(
                          "lead_ids",
                          current.filter((id) => id !== lead.id)
                        );
                      }
                    }}
                  />
                  <span className="text-sm">{lead.name || lead.phone_number}</span>
                </label>
              ))}
            </div>
          )}
        </div>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div>
          <Label htmlFor="max_concurrent_calls">Max concurrent</Label>
          <Input id="max_concurrent_calls" type="number" {...register("max_concurrent_calls")} />
        </div>
        <div>
          <Label htmlFor="retry_attempts">Retry attempts</Label>
          <Input id="retry_attempts" type="number" {...register("retry_attempts")} />
        </div>
        <div>
          <Label htmlFor="retry_delay_minutes">Retry delay (min)</Label>
          <Input id="retry_delay_minutes" type="number" {...register("retry_delay_minutes")} />
        </div>
      </div>
      <div className="flex gap-3">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Creating..." : "Create campaign"}
        </Button>
        <Button type="button" variant="ghost" onClick={() => router.push("/campaigns")}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
