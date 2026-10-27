import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Award as AwardIcon, Pencil, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/features/institutions/lib/format";
import { projectKeys, projectsApi } from "@/features/our-internships/api/projects-api";
import { type Award, awardsApi, reviewKeys } from "@/features/our-internships/api/reviews-api";
import { formatDateTime } from "@/features/our-internships/lib/learning";

const selectClass = "w-full rounded-md border bg-background px-3 py-2 text-sm";

/** Awards for the internship (Best Project, Top Performer...) and who holds them. Students see theirs on their profile. */
export function AwardsTab({ internshipId, canManage }: { internshipId: string; canManage: boolean }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Award | "new" | null>(null);
  const [granting, setGranting] = useState<Award | null>(null);
  const awards = useQuery({ queryKey: reviewKeys.awards(internshipId), queryFn: () => awardsApi.list(internshipId) });
  const refresh = () => queryClient.invalidateQueries({ queryKey: reviewKeys.awards(internshipId) });
  const remove = useMutation({ mutationFn: (id: string) => awardsApi.remove(internshipId, id), onSuccess: refresh });
  const revoke = useMutation({ mutationFn: (v: { awardId: string; selectionId: string }) => awardsApi.revoke(internshipId, v.awardId, v.selectionId), onSuccess: refresh });

  if (awards.isLoading) return <Skeleton className="h-40 w-full" />;
  if (awards.isError) return <p className="text-sm text-destructive">Could not load the awards.</p>;
  const items = awards.data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-muted-foreground">Create awards and give them to students who have LMS access. Each student sees their awards in the student portal.</p>
        {canManage && (
          <Button onClick={() => setEditing("new")}>
            <Plus className="h-4 w-4" />
            New award
          </Button>
        )}
      </div>
      {(remove.isError || revoke.isError) && <p className="text-sm text-destructive">{errorMessage(remove.error ?? revoke.error, "That did not work.")}</p>}

      {items.length === 0 ? (
        <p className="rounded-md border p-8 text-center text-sm text-muted-foreground">No awards yet.</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((award) => (
            <Card key={award.id}>
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <AwardIcon className="h-4 w-4 text-amber-500" />
                    {award.name}
                  </CardTitle>
                  {canManage && (
                    <div className="flex gap-1">
                      <Button size="icon" variant="ghost" aria-label={`Edit ${award.name}`} onClick={() => setEditing(award)}>
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label={`Delete ${award.name}`}
                        disabled={remove.isPending}
                        onClick={() => {
                          if (window.confirm(`Delete the award "${award.name}"? Students who hold it will lose it.`)) remove.mutate(award.id);
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  )}
                </div>
                {award.description && <CardDescription>{award.description}</CardDescription>}
              </CardHeader>
              <CardContent className="space-y-2">
                {award.grants.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Not given to anyone yet.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {award.grants.map((g) => (
                      <li key={g.selection_id} className="flex items-start justify-between gap-2 text-sm">
                        <div>
                          <span className="font-medium">{g.student_name}</span>
                          <span className="ml-2 text-xs text-muted-foreground">{formatDateTime(g.granted_at)}</span>
                          {g.note && <div className="text-xs text-muted-foreground">{g.note}</div>}
                        </div>
                        {canManage && (
                          <Button size="icon" variant="ghost" aria-label={`Take ${award.name} from ${g.student_name}`} disabled={revoke.isPending} onClick={() => revoke.mutate({ awardId: award.id, selectionId: g.selection_id })}>
                            <X className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                {canManage && (
                  <Button size="sm" variant="outline" onClick={() => setGranting(award)}>
                    Give to a student
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {editing && <AwardDialog internshipId={internshipId} award={editing === "new" ? null : editing} onClose={() => setEditing(null)} onSaved={() => void refresh()} />}
      {granting && <GrantDialog internshipId={internshipId} award={granting} onClose={() => setGranting(null)} onSaved={() => void refresh()} />}
    </div>
  );
}

function AwardDialog({ internshipId, award, onClose, onSaved }: { internshipId: string; award: Award | null; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(award?.name ?? "");
  const [description, setDescription] = useState(award?.description ?? "");
  const save = useMutation({
    mutationFn: () => {
      const body = { name: name.trim(), description: description.trim() || null };
      return award ? awardsApi.update(internshipId, award.id, body) : awardsApi.create(internshipId, body);
    },
    onSuccess: () => {
      onSaved();
      onClose();
    },
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{award ? "Edit award" : "New award"}</DialogTitle>
          <DialogDescription>For example Best Project, Top Performer or Most Improved.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="award-name">Name</Label>
            <Input id="award-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="award-desc">Description</Label>
            <Textarea id="award-desc" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not save the award.")}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button disabled={!name.trim() || save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? "Saving..." : "Save"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function GrantDialog({ internshipId, award, onClose, onSaved }: { internshipId: string; award: Award; onClose: () => void; onSaved: () => void }) {
  const [selectionId, setSelectionId] = useState("");
  const [note, setNote] = useState("");
  // only students with LMS access can be given an award
  const students = useQuery({ queryKey: projectKeys.selections(internshipId), queryFn: () => projectsApi.selections(internshipId) });
  const eligible = students.data ?? [];
  const holders = new Set(award.grants.map((g) => g.selection_id));
  const give = useMutation({
    mutationFn: () => awardsApi.grant(internshipId, award.id, selectionId, note.trim() || null),
    onSuccess: () => {
      onSaved();
      onClose();
    },
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Give "{award.name}"</DialogTitle>
          <DialogDescription>Only students with LMS access are listed.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <select aria-label="Student" className={selectClass} value={selectionId} onChange={(e) => setSelectionId(e.target.value)}>
            <option value="">Choose a student...</option>
            {eligible.map((s) => (
              <option key={s.selection_id} value={s.selection_id} disabled={holders.has(s.selection_id)}>
                {s.student_name}
                {holders.has(s.selection_id) ? " (already has it)" : ""}
              </option>
            ))}
          </select>
          {students.isSuccess && eligible.length === 0 && <p className="text-xs text-muted-foreground">No students have LMS access yet. Grant it under Onboarding.</p>}
          <Input aria-label="Note" placeholder="Why (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
          {give.isError && <p className="text-sm text-destructive">{errorMessage(give.error, "Could not give the award.")}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button disabled={!selectionId || give.isPending} onClick={() => give.mutate()}>
              Give award
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
