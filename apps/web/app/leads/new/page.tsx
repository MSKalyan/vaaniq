"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import { DashboardLayout } from "@/components/dashboard-layout";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { api } from "@/lib/api";

const schema = z.object({
  name: z.string().optional(),
  phone_number: z.string().min(8, "Valid phone number required"),
  email: z.string().email("Invalid email").optional().or(z.literal("")),
  language: z.string().optional(),
  location: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

export default function NewLeadPage() {
  const router = useRouter();
  const qc = useQueryClient();

  const create = useMutation({
    mutationFn: (data: FormValues) =>
      api.post("/leads", {
        ...data,
        email: data.email || undefined,
        name: data.name || undefined,
        language: data.language || undefined,
        location: data.location || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["leads"] });
      router.push("/leads");
      router.refresh();
    },
  });

  const { register, handleSubmit, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
  });

  return (
    <DashboardLayout>
      <h1 className="mb-6 text-2xl font-semibold">Add Lead</h1>
      <form
        onSubmit={handleSubmit((v) => create.mutate(v))}
        className="grid max-w-xl gap-4"
      >
        <div>
          <Label htmlFor="name">Name</Label>
          <Input id="name" {...register("name")} />
        </div>
        <div>
          <Label htmlFor="phone_number">Phone number</Label>
          <Input id="phone_number" {...register("phone_number")} placeholder="+919876543210" />
          {errors.phone_number && (
            <p className="mt-1 text-sm text-destructive">{errors.phone_number.message}</p>
          )}
        </div>
        <div>
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" {...register("email")} />
          {errors.email && (
            <p className="mt-1 text-sm text-destructive">{errors.email.message}</p>
          )}
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label htmlFor="language">Language</Label>
            <Input id="language" {...register("language")} placeholder="te-IN" />
          </div>
          <div>
            <Label htmlFor="location">Location</Label>
            <Input id="location" {...register("location")} />
          </div>
        </div>
        <div className="flex gap-3">
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Saving…" : "Create lead"}
          </Button>
          <Button type="button" variant="ghost" onClick={() => router.push("/leads")}>
            Cancel
          </Button>
        </div>
        {create.isError && (
          <p className="text-sm text-destructive">
            {(create.error as Error)?.message ?? "Failed to create lead"}
          </p>
        )}
      </form>
    </DashboardLayout>
  );
}