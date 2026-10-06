"use client";

import { useAnalyticsDashboard } from "@/hooks/use-analytics";
import { KpiCard } from "@/components/kpi-card";
import { DashboardLayout } from "@/components/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export default function AnalyticsPage() {
  const dashboard = useAnalyticsDashboard(30);

  if (dashboard.isLoading) {
    return (
      <DashboardLayout>
        <p className="text-muted-foreground">Loading analytics…</p>
      </DashboardLayout>
    );
  }

  if (dashboard.isError || !dashboard.data) {
    return (
      <DashboardLayout>
        <p className="text-destructive">Unable to load analytics.</p>
      </DashboardLayout>
    );
  }

  const { overview, campaigns, outcomes, languages, daily_volume: volume } = dashboard.data;
  const peak = volume.reduce((max, day) => Math.max(max, day.total), 0);

  return (
    <DashboardLayout>
      <h1 className="mb-6 text-2xl font-semibold">Analytics</h1>

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Total calls"
          value={overview.total_calls}
          hint={`${overview.in_progress_calls} in progress`}
        />
        <KpiCard
          label="Connection rate"
          value={percent(overview.connection_rate)}
          hint={`${overview.failed_calls} failed`}
        />
        <KpiCard
          label="Interested"
          value={overview.interested}
          hint={`${percent(overview.interest_rate)} of calls`}
        />
        <KpiCard
          label="Callbacks"
          value={overview.callback_requested}
          hint={`${percent(overview.callback_rate)} of calls`}
        />
        <KpiCard
          label="Avg duration"
          value={`${overview.average_call_duration_seconds.toFixed(0)}s`}
          hint={`${overview.average_call_latency_ms.toFixed(0)} ms avg latency`}
        />
        <KpiCard label="Leads" value={overview.total_leads} />
        <KpiCard
          label="Not interested"
          value={overview.not_interested}
        />
        <KpiCard
          label="Do not call"
          value={overview.do_not_call}
          hint="Never dial these again"
        />
      </div>

      <div className="mb-6 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Daily call volume (30 days)</CardTitle>
          </CardHeader>
          <CardContent>
            {volume.length === 0 ? (
              <p className="text-sm text-muted-foreground">No calls recorded yet.</p>
            ) : (
              <div className="flex h-40 items-end gap-1">
                {volume.map((day) => (
                  <div
                    key={day.day ?? "unknown"}
                    className="group relative flex flex-1 flex-col justify-end"
                    title={`${day.day ?? "unknown"}: ${day.total} calls, ${day.connected} connected`}
                  >
                    <div
                      className="w-full rounded-t bg-primary"
                      style={{
                        height: peak ? `${(day.total / peak) * 100}%` : "0%",
                      }}
                    />
                    <div
                      className="w-full rounded-t bg-primary-foreground/40"
                      style={{
                        height: peak ? `${(day.connected / peak) * 100}%` : "0%",
                      }}
                    />
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Outcomes</CardTitle>
          </CardHeader>
          <CardContent>
            {outcomes.length === 0 ? (
              <p className="text-sm text-muted-foreground">No outcomes yet.</p>
            ) : (
              <ul className="flex flex-col gap-2 text-sm">
                {outcomes.map((row) => (
                  <li key={row.outcome} className="flex items-center justify-between gap-3">
                    <span>{row.outcome.replace(/_/g, " ")}</span>
                    <span className="text-muted-foreground">{row.count}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Languages</CardTitle>
          </CardHeader>
          <CardContent>
            {languages.length === 0 ? (
              <p className="text-sm text-muted-foreground">No language data yet.</p>
            ) : (
              <ul className="flex flex-col gap-2 text-sm">
                {languages.map((row) => (
                  <li key={row.language} className="flex items-center justify-between gap-3">
                    <span>{row.language}</span>
                    <span className="text-muted-foreground">{row.count}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Campaign performance</CardTitle>
          </CardHeader>
          <CardContent>
            {campaigns.length === 0 ? (
              <p className="text-sm text-muted-foreground">No campaigns yet.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="border-b text-left text-muted-foreground">
                  <tr>
                    <th className="p-2 font-medium">Campaign</th>
                    <th className="p-2 font-medium">Status</th>
                    <th className="p-2 font-medium">Leads</th>
                    <th className="p-2 font-medium">Connected</th>
                    <th className="p-2 font-medium">Interested</th>
                  </tr>
                </thead>
                <tbody>
                  {campaigns.map((campaign) => (
                    <tr key={campaign.campaign_id} className="border-b last:border-0">
                      <td className="p-2">{campaign.name}</td>
                      <td className="p-2 text-muted-foreground">{campaign.status}</td>
                      <td className="p-2">{campaign.total_leads}</td>
                      <td className="p-2">
                        {campaign.calls_connected}
                        <span className="ml-1 text-xs text-muted-foreground">
                          ({percent(campaign.connection_rate)})
                        </span>
                      </td>
                      <td className="p-2">{campaign.interested}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}