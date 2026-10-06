"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { LogOut } from "lucide-react";

import { useCurrentUser, useLogout } from "@/hooks/use-auth";
import { getAccessToken } from "@/lib/api";
import { Sidebar } from "@/components/sidebar";
import { Button } from "@/components/ui/button";

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const me = useCurrentUser();
  const logout = useLogout();

  // No token means nothing behind this layout can load; bounce to sign-in.
  useEffect(() => {
    if (!getAccessToken()) router.replace("/login");
  }, [router]);

  useEffect(() => {
    if (me.isError) router.replace("/login");
  }, [me.isError, router]);

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="flex h-14 items-center justify-between border-b px-6">
          <div className="text-sm text-muted-foreground">VoiceAI</div>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-muted-foreground">{me.data?.email ?? "Account"}</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() =>
                logout.mutate(undefined, { onSettled: () => router.replace("/login") })
              }
            >
              <LogOut className="h-4 w-4" /> Sign out
            </Button>
          </div>
        </header>
        <div className="flex-1 overflow-auto p-6">{children}</div>
      </main>
    </div>
  );
}