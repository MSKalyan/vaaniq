"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Sparkles } from "lucide-react";

import { DashboardLayout } from "@/components/dashboard-layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCall, useEndCall, useRunAnalysis } from "@/hooks/use-calls";

function formatDuration(seconds: number | null): string {
  if (seconds === null) return "—";
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

function stringify(value: unknown): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

export default function CallDetailPage() {
  const params = useParams<{ id: string }>();
  const callId = params.id;
  const call = useCall(callId);
  const runAnalysis = useRunAnalysis(callId);
  const endCall = useEndCall();

  if (call.isLoading) {
    return (
      <DashboardLayout>
        <p className="text-muted-foreground">Loading call…</p>
      </DashboardLayout>
    );
  }

  if (call.isError || !call.data) {
    return (
      <DashboardLayout>
        <p className="text-destructive">Unable to load this call.</p>
      </DashboardLayout>
    );
  }

  const data = call.data;
  const latency = Object.entries(data.latency_ms ?? {});

  return (
    <DashboardLayout>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link href="/calls">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4" /> Calls
            </Button>
          </Link>
          <h1 className="text-2xl font-semibold">
            {data.lead_name ?? data.phone_number ?? "Call"}
          </h1>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => runAnalysis.mutate()}
            disabled={runAnalysis.isPending}
          >
            <Sparkles className="h-4 w-4" />
            {runAnalysis.isPending ? "Analyzing…" : "Generate summary"}
          </Button>
          {data.state !== "COMPLETED" && data.state !== "FAILED" && (
            <Button variant="destructive" onClick={() => endCall.mutate(callId)} disabled={endCall.isPending}>
              End call
            </Button>
          )}
        </div>
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">State</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-semibold">{data.state}</p>
            <p className="text-sm text-muted-foreground">{data.outcome ?? "No outcome yet"}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Duration</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-semibold">{formatDuration(data.duration_seconds)}</p>
            <p className="text-sm text-muted-foreground">{data.direction}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Agent</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-semibold">{data.agent_name ?? "—"}</p>
            <p className="truncate text-sm text-muted-foreground">{data.provider_call_id ?? "—"}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Latency</CardTitle>
          </CardHeader>
          <CardContent>
            {latency.length === 0 ? (
              <p className="text-sm text-muted-foreground">No metrics recorded</p>
            ) : (
              <ul className="text-sm">
                {latency.map(([stage, value]) => (
                  <li key={stage} className="flex justify-between gap-2">
                    <span className="text-muted-foreground">{stage.replace(/_/g, " ")}</span>
                    <span>{Math.round(value)} ms</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Transcript</CardTitle>
          </CardHeader>
          <CardContent>
            {data.transcript.length === 0 ? (
              <p className="text-sm text-muted-foreground">No transcript recorded.</p>
            ) : (
              <ol className="flex flex-col gap-3">
                {data.transcript.map((turn) => (
                  <li key={turn.id} className="flex flex-col">
                    <span className="text-xs uppercase tracking-wide text-muted-foreground">
                      {turn.speaker}
                      {turn.language ? ` · ${turn.language}` : ""}
                    </span>
                    <span className="text-sm">{turn.text}</span>
                  </li>
                ))}
              </ol>
            )}
          </CardContent>
        </Card>

        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              {runAnalysis.isError && (
                <p className="mb-2 text-sm text-destructive">
                  {(runAnalysis.error as Error)?.message ?? "Analysis failed"}
                </p>
              )}
              {!data.analysis ? (
                <p className="text-sm text-muted-foreground">
                  No analysis yet. Use &ldquo;Generate summary&rdquo; to run it.
                </p>
              ) : (
                <div className="flex flex-col gap-3 text-sm">
                  <div className="flex flex-wrap gap-2">
                    {data.analysis.sentiment && (
                      <span className="rounded bg-secondary px-2 py-0.5 text-xs">
                        {data.analysis.sentiment}
                      </span>
                    )}
                    {data.analysis.intent && (
                      <span className="rounded bg-secondary px-2 py-0.5 text-xs">
                        {data.analysis.intent}
                      </span>
                    )}
                    {data.analysis.interest_level && (
                      <span className="rounded bg-secondary px-2 py-0.5 text-xs">
                        interest: {data.analysis.interest_level}
                      </span>
                    )}
                  </div>
                  {data.analysis.summary && <p>{data.analysis.summary}</p>}
                  {data.analysis.next_action && (
                    <p>
                      <span className="text-muted-foreground">Next: </span>
                      {data.analysis.next_action}
                    </p>
                  )}
                  {data.analysis.callback_required && (
                    <p className="text-sm">
                      <span className="text-muted-foreground">Callback: </span>
                      {data.analysis.callback_time ?? "requested"}
                    </p>
                  )}
                  {data.analysis.key_points.length > 0 && (
                    <div>
                      <p className="mb-1 text-muted-foreground">Key points</p>
                      <ul className="list-disc pl-4">
                        {data.analysis.key_points.map((point, index) => (
                          <li key={index}>{stringify(point)}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {data.analysis.objections.length > 0 && (
                    <div>
                      <p className="mb-1 text-muted-foreground">Objections</p>
                      <ul className="list-disc pl-4">
                        {data.analysis.objections.map((objection, index) => (
                          <li key={index}>{stringify(objection)}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {Object.keys(data.analysis.extracted_data ?? {}).length > 0 && (
                    <div>
                      <p className="mb-1 text-muted-foreground">Extracted data</p>
                      <pre className="overflow-x-auto rounded bg-secondary/50 p-2 text-xs">
                        {JSON.stringify(data.analysis.extracted_data, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recording</CardTitle>
            </CardHeader>
            <CardContent>
              {!data.recording || !data.recording.recording_url ? (
                <p className="text-sm text-muted-foreground">
                  {data.recording ? "Recording not available yet." : "No recording requested."}
                </p>
              ) : (
                <audio
                  controls
                  src={data.recording.recording_url}
                  className="w-full"
                  aria-label="Call recording"
                />
              )}
              {data.error_message && (
                <p className="mt-3 text-sm text-destructive">{data.error_message}</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
}