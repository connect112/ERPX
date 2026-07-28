import { ArrowLeft, Pencil, Trash2 } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
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
import { useDeleteLab, useLab, useUpdateLab } from "@/features/pentrix/labs/api/labs-hooks";
import { LabFormDialog } from "@/features/pentrix/labs/pages/lab-form-dialog";
import { labDifficultyLabels } from "@/features/pentrix/labs/schemas/lab-schemas";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function LabDetailPage() {
  const { labId } = useParams<{ labId: string }>();
  const navigate = useNavigate();
  const { data: lab, isLoading } = useLab(labId);
  const updateLab = useUpdateLab(labId ?? "");
  const deleteLab = useDeleteLab();

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  if (isLoading || !lab) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const handleDelete = () => {
    deleteLab.mutate(lab.id, { onSuccess: () => navigate("/pentrix/labs") });
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/pentrix/labs")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{lab.title}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="text-xs text-muted-foreground">{lab.slug}</span>
              <Badge variant={lab.is_active ? "success" : "secondary"}>
                {lab.is_active ? "Active" : "Inactive"}
              </Badge>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => updateLab.mutate({ is_active: !lab.is_active })}
            disabled={updateLab.isPending}
          >
            {lab.is_active ? "Deactivate" : "Activate"}
          </Button>
          <Button variant="outline" onClick={() => setEditOpen(true)}>
            <Pencil className="h-4 w-4" />
            Edit
          </Button>
          <Button variant="outline" onClick={() => setDeleteOpen(true)}>
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Lab details</CardTitle>
        </CardHeader>
        <CardContent>
          {lab.description && <p className="pb-3 text-sm text-muted-foreground">{lab.description}</p>}
          <DetailRow label="Category" value={lab.category} />
          <DetailRow label="Difficulty" value={labDifficultyLabels[lab.difficulty]} />
          <DetailRow label="Environment image" value={lab.environment_image} />
          <DetailRow label="Points" value={lab.points} />
          <DetailRow label="Default duration" value={`${lab.default_duration_minutes} minutes`} />
        </CardContent>
      </Card>

      <p className="text-sm text-muted-foreground">
        Students launch instances of this lab from their own profile's Pentrix tab.
      </p>

      <LabFormDialog open={editOpen} onOpenChange={setEditOpen} lab={lab} />

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete lab</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete <span className="font-medium">{lab.title}</span>? This
            action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteLab.isPending}>
              {deleteLab.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
