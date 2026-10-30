import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useUsage } from "@/features/storage-manager/api/storage-hooks";
import { formatBytes } from "@/features/storage-manager/lib/format";

const COLORS = ["#2563eb", "#16a34a", "#f59e0b", "#dc2626", "#7c3aed", "#0891b2", "#db2777", "#65a30d", "#64748b"];

function Stat({ label, value, hint, onClick }: { label: string; value: string; hint?: string; onClick?: () => void }) {
  const body = (
    <CardContent className="p-5">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </CardContent>
  );
  return onClick ? (
    <button type="button" onClick={onClick} className="text-left">
      <Card className="h-full transition-colors hover:bg-accent/40">{body}</Card>
    </button>
  ) : (
    <Card>{body}</Card>
  );
}

export function OverviewPanel({ onShow }: { onShow: (status: string) => void }) {
  const { data, isLoading, isError } = useUsage();

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (isError || !data) return <p className="text-sm text-destructive">Storage figures could not be loaded.</p>;
  const files = data.files;

  const bySource = files.by_source.map((s) => ({ name: s.label, bytes: s.bytes, count: s.count }));
  const byType = files.by_type.map((t) => ({ name: t.type_group, value: t.bytes }));

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        {data.scope === "platform" ? "Every organization on the platform." : "Your organization's files."} Sizes are the
        stored files themselves: database storage, Docker and the server are on the Server tab.
      </p>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Files" value={files.total_count.toLocaleString()} hint={formatBytes(files.total_bytes)} />
        <Stat
          label="Unused files"
          value={formatBytes(files.orphan_bytes)}
          hint={`${files.orphan_count} not used by any record`}
          onClick={() => onShow("orphan")}
        />
        <Stat label="Duplicates" value={formatBytes(files.duplicate_wasted_bytes)} hint={`${files.duplicate_groups} groups of identical files`} />
        <Stat label="In Trash" value={formatBytes(files.trash_bytes)} hint={`${files.trash_count} files, recoverable`} />
        <Stat label="Large files (10 MB+)" value={files.large_count.toLocaleString()} hint={formatBytes(files.large_bytes)} />
        <Stat label="Protected" value={files.protected_count.toLocaleString()} hint={`${formatBytes(files.protected_bytes)}, cannot be deleted here`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Space by source</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            {bySource.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted-foreground">No files yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={bySource} layout="vertical" margin={{ left: 20 }}>
                  <XAxis type="number" tickFormatter={(v: number) => formatBytes(v)} />
                  <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 12 }} />
                  <Tooltip formatter={(value: number) => formatBytes(value)} />
                  <Bar dataKey="bytes" fill="#2563eb" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Space by file type</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            {byType.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted-foreground">No files yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={byType} dataKey="value" nameKey="name" innerRadius={55} outerRadius={95} label={(entry: { name: string }) => entry.name}>
                    {byType.map((_, index) => (
                      <Cell key={index} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: number) => formatBytes(value)} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
