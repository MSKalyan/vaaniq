"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useLogin } from "@/hooks/use-auth";
import { getAccessToken } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const login = useLogin();

  // Already signed in? Skip the form.
  useEffect(() => {
    if (getAccessToken()) router.replace("/dashboard");
  }, [router]);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <h1 className="mb-6 text-center text-2xl font-semibold">Sign in to VoiceAI</h1>
        <form
          onSubmit={handleSubmit((values) =>
            login.mutate(values, { onSuccess: () => router.replace("/dashboard") })
          )}
          className="grid gap-4"
        >
          <div>
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="email" {...register("email")} />
            {errors.email && (
              <p className="mt-1 text-sm text-destructive">{errors.email.message}</p>
            )}
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              {...register("password")}
            />
            {errors.password && (
              <p className="mt-1 text-sm text-destructive">{errors.password.message}</p>
            )}
          </div>
          <Button type="submit" disabled={login.isPending}>
            {login.isPending ? "Signing in…" : "Sign in"}
          </Button>
          {login.isError && (
            <p className="text-sm text-destructive">
              {(login.error as Error)?.message ?? "Sign in failed"}
            </p>
          )}
        </form>
        <p className="mt-4 text-center text-sm text-muted-foreground">
          No account yet?{" "}
          <Link href="/register" className="underline">
            Create one
          </Link>
        </p>
      </div>
    </main>
  );
}