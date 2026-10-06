"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { getAccessToken } from "@/lib/api";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace(getAccessToken() ? "/dashboard" : "/login");
  }, [router]);

  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <p className="text-muted-foreground">Loading VoiceAI…</p>
    </main>
  );
}