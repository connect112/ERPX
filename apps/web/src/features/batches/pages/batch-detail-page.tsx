import { ArrowLeft, Trash2 } from "lucide-react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useBatch, useDeleteBatch, useUpdateBatch } from "@/features/batches/api/batches-hooks";
import { type BatchStatus } from "@/features/batches/api/batches-api";
import { BatchStatusBadge } from "@/features/batches/components/batch-status-badge";
import { useCoursesList } from "@/features/courses/api/courses-hooks";
import { LiveClassesPanel } from "@/features/live-classes/components/live-classes-panel";
import { TimetablePanel } from "@/features/timetable/components/timetable-panel";
import { useTrainersList } from "@/features/trainers/api/trainers-hooks";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

const statusValues: BatchStatus[] = ["upcoming", "ongoing", "completed", "cancelled"];
const statusLabels: Record<BatchStatus, string> = {
  upcoming: "Upcoming",
  ongoing: "Ongoing",
  completed: "Completed",
  cancelled: "Cancelled",
};

export function BatchDetailPage() {
  const { batchId } = useParams<{ batchId: string }>();
  const navigate = useNavigate();
  const { data: batch, isLoading } = useBatch(batchId);
  const { data: courses } = useCoursesList({ limit: 200 });
  const { data: trainers } = useTrainersList({ limit: 200 });
  const updateBatch = useUpdateBatch(batchId ?? "");
  const deleteBatch = useDeleteBatch();

  const [deleteOpen, setDeleteOpen] = useState(false);

  if (isLoading || !batch) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const course = courses?.items.find((c) => c.id === batch.course_id);
  const trainer = trainers?.items.find((t) => t.id === batch.trainer_id);

  const handleDelete = () => {
    deleteBatch.mutate(batch.id, { onSuccess: () => navigate("/batches") });
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/batches")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{batch.name}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">{batch.code}</span>
              <BatchStatusBadge status={batch.status} />
            </div>
          </div>
        </div>
        <Button variant="outline" onClick={() => setDeleteOpen(true)}>
          <Trash2 className="h-4 w-4" />
          Delete
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Batch details</CardTitle>
            </CardHeader>
            <CardContent>
              <DetailRow label="Course" value={course?.title ?? "—"} />
              <DetailRow label="Trainer" value={trainer?.employee_name ?? "Unassigned"} />
              <DetailRow label="Start date" value={new Date(batch.start_date).toLocaleDateString()} />
              <DetailRow
                label="End date"
                value={batch.end_date ? new Date(batch.end_date).toLocaleDateString() : "—"}
              />
              <DetailRow label="Capacity" value={batch.capacity ?? "—"} />
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Change status</CardTitle>
          </CardHeader>
          <CardContent>
            <Select
              value={batch.status}
              onValueChange={(value) => updateBatch.mutate({ status: value as BatchStatus })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {statusValues.map((s) => (
                  <SelectItem key={s} value={s}>
                    {statusLabels[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>
      </div>

      <TimetablePanel batchId={batch.id} />
      <LiveClassesPanel batchId={batch.id} />

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete batch</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete <span className="font-medium">{batch.name}</span>? This
            action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteBatch.isPending}>
              {deleteBatch.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
