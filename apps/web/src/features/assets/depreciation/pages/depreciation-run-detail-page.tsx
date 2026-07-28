import { ArrowLeft } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAssetsList } from "@/features/assets/assets/api/assets-hooks";
import {
  useCancelDepreciationRun,
  useDepreciationEntries,
  useDepreciationRun,
  usePostDepreciationRun,
} from "@/features/assets/depreciation/api/depreciation-hooks";
import { DepreciationRunStatusBadge } from "@/features/assets/depreciation/components/depreciation-run-status-badge";

const monthNames = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function DepreciationRunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { data: run, isLoading } = useDepreciationRun(runId);
  const { data: entries, isLoading: entriesLoading } = useDepreciationEntries(runId);
  const { data: assets } = useAssetsList({ limit: 200 });

  const postRun = usePostDepreciationRun(runId ?? "");
  const cancelRun = useCancelDepreciationRun(runId ?? "");
  const [cancelOpen, setCancelOpen] = useState(false);

  const assetName = (id: string) => assets?.items.find((a) => a.id === id)?.name ?? id;

  if (isLoading || !run) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/assets/depreciation-runs")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {monthNames[run.period_month - 1]} {run.period_year} Depreciation
            </h1>
            <div className="mt-1">
              <DepreciationRunStatusBadge status={run.status} />
            </div>
          </div>
        </div>
        {run.status === "draft" && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => postRun.mutate()} disabled={postRun.isPending}>
              {postRun.isPending ? "Posting..." : "Post"}
            </Button>
            <Button variant="outline" onClick={() => setCancelOpen(true)}>
              Cancel
            </Button>
          </div>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <DetailRow label="Run date" value={new Date(run.run_date).toLocaleDateString()} />
          <DetailRow label="Total depreciation" value={run.total_depreciation_amount.toLocaleString()} />
          {run.posted_at && <DetailRow label="Posted at" value={new Date(run.posted_at).toLocaleString()} />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Depreciation entries</CardTitle>
        </CardHeader>
        <CardContent>
          {entriesLoading && <Skeleton className="h-32 w-full" />}
          {!entriesLoading && (entries?.length ?? 0) === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">No entries generated.</p>
          )}
          {!entriesLoading && (entries?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Asset</TableHead>
                  <TableHead>Depreciation amount</TableHead>
                  <TableHead>Accumulated depreciation</TableHead>
                  <TableHead>Net book value</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries?.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="font-medium">{assetName(entry.asset_id)}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {entry.depreciation_amount.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {entry.accumulated_depreciation.toLocaleString()}
                    </TableCell>
                    <TableCell className="font-medium">{entry.net_book_value.toLocaleString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel depreciation run</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to cancel this depreciation run? This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCancelOpen(false)}>
              Keep run
            </Button>
            <Button
              variant="destructive"
              onClick={() => cancelRun.mutate(undefined, { onSuccess: () => setCancelOpen(false) })}
              disabled={cancelRun.isPending}
            >
              {cancelRun.isPending ? "Cancelling..." : "Cancel run"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
