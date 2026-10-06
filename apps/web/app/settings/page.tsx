"use client";

import { CheckCircle2, XCircle } from "lucide-react";

import { DashboardLayout } from "@/components/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSettings, useVoices } from "@/hooks/use-settings";

export default function SettingsPage() {
  const settings = useSettings();
  const voices = useVoices();

  const languages = Array.from(
    new Set((voices.data ?? []).map((voice) => voice.language)),
  ).sort();

  return (
    <DashboardLayout>
      <h1 className="mb-6 text-2xl font-semibold">Settings</h1>

      {settings.isError && (
        <p className="mb-4 text-destructive">Unable to load settings.</p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Providers</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-4 text-sm text-muted-foreground">
              Each capability is swappable by environment variable. Secrets are never returned
              here — only whether credentials are present.
            </p>
            {settings.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {(settings.data?.providers ?? []).map((provider) => (
                  <li
                    key={provider.capability}
                    className="flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm"
                  >
                    <span className="flex items-center gap-2">
                      {provider.configured ? (
                        <CheckCircle2 className="h-4 w-4 text-green-600" />
                      ) : (
                        <XCircle className="h-4 w-4 text-destructive" />
                      )}
                      <span className="uppercase">{provider.capability}</span>
                    </span>
                    <span className="text-right text-muted-foreground">
                      {provider.provider}
                      {provider.model ? ` · ${provider.model}` : ""}
                      {!provider.configured ? " · no credentials" : ""}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Call defaults</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="flex flex-col gap-2 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Environment</dt>
                <dd>{settings.data?.app_env ?? "—"}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Max call duration</dt>
                <dd>
                  {settings.data
                    ? `${settings.data.default_max_call_duration_seconds}s`
                    : "—"}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Silence timeout</dt>
                <dd>
                  {settings.data ? `${settings.data.default_silence_timeout_seconds}s` : "—"}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Frontend URL</dt>
                <dd className="truncate">{settings.data?.frontend_url ?? "—"}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>
              Voice catalog{" "}
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                {voices.data?.length ?? 0} voices across {languages.length} languages
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {voices.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading voices…</p>
            ) : voices.isError ? (
              <p className="text-sm text-destructive">Unable to load voices.</p>
            ) : languages.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No voices loaded. Seed the voice catalog before creating agents.
              </p>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {languages.map((language) => (
                  <div key={language}>
                    <p className="mb-2 text-sm font-medium">{language}</p>
                    <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
                      {(voices.data ?? [])
                        .filter((voice) => voice.language === language)
                        .map((voice) => (
                          <li key={voice.id}>
                            {voice.voice_name}
                            {voice.provider ? ` · ${voice.provider}` : ""}
                          </li>
                        ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}