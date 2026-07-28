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
import { useChallenge, useDeleteChallenge, useUpdateChallenge } from "@/features/pentrix/challenges/api/challenges-hooks";
import { ChallengeFormDialog } from "@/features/pentrix/challenges/pages/challenge-form-dialog";
import { FlagPanel } from "@/features/pentrix/flags/components/flag-panel";
import { HintsPanel } from "@/features/pentrix/hints/components/hints-panel";
import { useLabs } from "@/features/pentrix/labs/api/labs-hooks";
import { labDifficultyLabels } from "@/features/pentrix/labs/schemas/lab-schemas";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function ChallengeDetailPage() {
  const { challengeId } = useParams<{ challengeId: string }>();
  const navigate = useNavigate();
  const { data: challenge, isLoading } = useChallenge(challengeId);
  const { data: labs } = useLabs();
  const updateChallenge = useUpdateChallenge(challengeId ?? "");
  const deleteChallenge = useDeleteChallenge();

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  if (isLoading || !challenge) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const labTitle = labs?.find((l) => l.id === challenge.lab_id)?.title;

  const handleDelete = () => {
    deleteChallenge.mutate(challenge.id, { onSuccess: () => navigate("/pentrix/challenges") });
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/pentrix/challenges")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{challenge.title}</h1>
            <div className="mt-1 flex items-center gap-2">
              <Badge variant="outline">{challenge.category}</Badge>
              <Badge variant={challenge.is_active ? "success" : "secondary"}>
                {challenge.is_active ? "Active" : "Inactive"}
              </Badge>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => updateChallenge.mutate({ is_active: !challenge.is_active })}
            disabled={updateChallenge.isPending}
          >
            {challenge.is_active ? "Deactivate" : "Activate"}
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
          <CardTitle className="text-base">Challenge details</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="pb-3 text-sm text-muted-foreground">{challenge.description}</p>
          <DetailRow label="Difficulty" value={labDifficultyLabels[challenge.difficulty]} />
          <DetailRow label="Points" value={challenge.points} />
          <DetailRow label="Linked lab" value={labTitle ?? "Standalone"} />
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <FlagPanel challengeId={challenge.id} />
        <HintsPanel challengeId={challenge.id} />
      </div>

      <ChallengeFormDialog open={editOpen} onOpenChange={setEditOpen} challenge={challenge} />

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete challenge</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete <span className="font-medium">{challenge.title}</span>?
            This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteChallenge.isPending}>
              {deleteChallenge.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
