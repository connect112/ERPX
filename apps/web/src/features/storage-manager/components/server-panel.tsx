import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useServerStatus } from "@/features/storage-manager/api/storage-hooks";
import { formatBytes, formatDate, percent } from "@/features/storage-manager/lib/format";

/** Read-only. There is no button on this tab that changes anything, and the server never runs a command for it. */
export function ServerPanel({ active }: { active: boolean }) {
  const { data, isLoading, isError } = useServerStatus(active);

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (isError || !data) return <p className="text-sm text-destructive">The server inspector is only available to platform superusers.</p>;

  const host = data.host;
  const total = host.disk_total_bytes ?? 0;
  const free = host.disk_free_bytes ?? 0;
  const used = total - free;
  const usedPercent = percent(used, total);
  const tables = data.database.top_tables.map((t) => ({ name: t.table, bytes: t.bytes }));

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">Read-only view of the database, object storage and the host. Nothing here can be changed or deleted.</p>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Server disk</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {host.available && total > 0 ? (
              <>
                <p className="text-2xl font-semibold">{usedPercent}% used</p>
                <div className="h-2 w-full overflow-hidden rounded bg-muted" role="progressbar" aria-valuenow={usedPercent} aria-valuemin={0} aria-valuemax={100}>
                  <div className={usedPercent >= 90 ? "h-full bg-red-600" : usedPercent >= 80 ? "h-full bg-amber-500" : "h-full bg-emerald-600"} style={{ width: `${usedPercent}%` }} />
                </div>
                <p className="text-sm text-muted-foreground">
                  {formatBytes(free)} free of {formatBytes(total)} · checked {formatDate(host.checked_at)}
                </p>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">{host.reason ?? "Host figures are not available."}</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Database</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{formatBytes(data.database.total_bytes)}</p>
            <p className="text-sm text-muted-foreground">{data.database.name}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Object storage</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{formatBytes(data.object_storage.total_bytes)}</p>
            <p className="text-sm text-muted-foreground">
              {data.object_storage.object_count.toLocaleString()} objects · {formatBytes(data.object_storage.in_app_backups_bytes)} in-app backups · {formatBytes(data.object_storage.trash_bytes)} Trash
            </p>
          </CardContent>
        </Card>
      </div>

      {host.alerts && host.alerts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Open storage and backup problems</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1 text-sm">
              {host.alerts.map((alert) => (
                <li key={alert.name} className={alert.severity === "critical" ? "text-destructive" : "text-amber-700"}>
                  [{alert.severity}] {alert.message}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Largest database tables</CardTitle>
        </CardHeader>
        <CardContent className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={tables} layout="vertical" margin={{ left: 30 }}>
              <XAxis type="number" tickFormatter={(v: number) => formatBytes(v)} />
              <YAxis type="category" dataKey="name" width={190} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(value: number) => formatBytes(value)} />
              <Bar dataKey="bytes" fill="#7c3aed" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {host.docker_df && host.docker_df.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Docker</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead className="text-left text-muted-foreground">
                <tr>
                  <th className="py-1">Type</th>
                  <th>Count</th>
                  <th>Size</th>
                  <th>Reclaimable</th>
                </tr>
              </thead>
              <tbody>
                {host.docker_df.map((row) => (
                  <tr key={row.Type} className="border-t">
                    <td className="py-1">{row.Type}</td>
                    <td>{row.TotalCount}</td>
                    <td>{row.Size}</td>
                    <td>{row.Reclaimable}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
